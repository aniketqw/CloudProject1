"""Account sessions and ownership for public customer access; no domain state bypasses."""
import hashlib,json,re,secrets,sqlite3,time,uuid
from threading import BoundedSemaphore
from contextlib import contextmanager

PASSWORD_SLOTS=BoundedSemaphore(2)
@contextmanager
def password_work():
    if not PASSWORD_SLOTS.acquire(timeout=1):raise TooManyRequests('Sign-in is busy. Please try again shortly.')
    try:yield
    finally:PASSWORD_SLOTS.release()
from datetime import datetime,timezone
from flask import request
from werkzeug.exceptions import BadRequest,Conflict,Forbidden,NotFound,TooManyRequests,Unauthorized
from werkzeug.security import generate_password_hash,check_password_hash

class Access:
    def __init__(self,state,api):
        self.state,self.api=state,api
        with state.connection() as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS web_accounts(id TEXT PRIMARY KEY,email TEXT NOT NULL UNIQUE,
              password_hash TEXT NOT NULL,name TEXT NOT NULL,home_workspace TEXT NOT NULL,created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS web_auth(session_id TEXT PRIMARY KEY,owner TEXT NOT NULL,
              account_id TEXT,role TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS web_workspace_owners(workspace_id TEXT PRIMARY KEY,owner TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS web_workspace_owner ON web_workspace_owners(owner);
            CREATE TABLE IF NOT EXISTS web_restaurant_fleets(restaurant_id TEXT PRIMARY KEY,data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS web_limits(bucket TEXT PRIMARY KEY,count INTEGER NOT NULL,expires REAL NOT NULL);
            """)
        self.dummy=generate_password_hash(secrets.token_urlsafe(32),method='scrypt')
    def identity(self,sid):
        with self.state.connection() as c:
            row=c.execute('SELECT * FROM web_auth WHERE session_id=?',(sid,)).fetchone()
            if row and row['expires']>time.time():return dict(row)
            if row:return None
            value={'session_id':sid,'owner':str(uuid.uuid4()),'account_id':None,'role':'guest','expires':time.time()+30*86400}
            c.execute('INSERT INTO web_auth VALUES(:session_id,:owner,:account_id,:role,:expires)',value)
            return value
    def limit(self,kind,identity,maximum=10,seconds=900):
        key=hashlib.sha256((kind+':'+identity).encode()).hexdigest();now=time.time()
        with self.state.connection() as c:
            c.execute('BEGIN IMMEDIATE');c.execute('DELETE FROM web_limits WHERE expires<?',(now,))
            row=c.execute('SELECT count FROM web_limits WHERE bucket=?',(key,)).fetchone()
            if row and row['count']>=maximum:raise TooManyRequests('Please wait before trying this action again.')
            c.execute('INSERT INTO web_limits VALUES(?,1,?) ON CONFLICT(bucket) DO UPDATE SET count=count+1',(key,now+seconds))
    def owns(self,owner,wid):
        with self.state.connection() as c:return bool(c.execute('SELECT 1 FROM web_workspace_owners WHERE owner=? AND workspace_id=?',(owner,wid)).fetchone())
    def workspaces(self,owner):
        with self.state.connection() as c:
            rows=c.execute('SELECT w.data FROM workspaces w JOIN web_workspace_owners o ON o.workspace_id=w.id WHERE o.owner=? ORDER BY w.rowid DESC LIMIT 100',(owner,)).fetchall()
        return [json.loads(x['data']) for x in rows]
    def bind(self,owner,w):
        with self.state.connection() as c:c.execute('INSERT INTO web_workspace_owners VALUES(?,?)',(w['id'],owner))
    def guest(self,sid,identity):
        context=self.context(sid);wid=context.get('workspace_id')
        if wid and self.owns(identity['owner'],wid):return self.state.workspace(wid)
        self.limit('guest-ip',request.remote_addr or 'unknown',20,3600)
        self.limit('guest-session',identity['owner'],3,3600)
        wid=str(uuid.uuid4());customer=self.api.call('customer','POST','/customers',{'name':'Guest diner','email':'guest-'+wid+'@example.test'})['customer']
        w={'id':wid,'name':'Your table','status':'READY','customer_id':customer['id'],'restaurant_id':None,'couriers':[],
           'zone':None,'run_id':wid,'orders':[],'created_at':datetime.now(timezone.utc).isoformat()}
        self.state.save_workspace(w);self.bind(identity['owner'],w);self.state.patch_context(sid,{'workspace_id':wid,'cart':{}},replace=True);return w
    def attach_restaurant(self,wid,rid):
        with self.state.connection() as c:
            row=c.execute('SELECT data FROM web_restaurant_fleets WHERE restaurant_id=?',(rid,)).fetchone()
            sources=c.execute("SELECT data FROM workspaces WHERE json_extract(data,'$.restaurant_id')=? AND json_extract(data,'$.zone') IS NOT NULL AND json_extract(data,'$.status')='READY' AND json_array_length(data,'$.couriers')>0 ORDER BY rowid LIMIT 1",(rid,)).fetchall()
        fleet=json.loads(row['data']) if row else None
        if not fleet and sources:
            original=json.loads(sources[0]['data']);fleet={k:original[k] for k in ['zone','couriers','run_id']}
        if not fleet:
            digest=hashlib.sha256(rid.encode()).hexdigest()[:20];zone='public-'+digest
            result=self.api.call('delivery','POST','/delivery/zones',{'zone':zone,'scenario':'manual'},key='public-zone:'+digest)
            fleet={'zone':zone,'run_id':result['run_id'],'couriers':[]}
            for name in ['A','B']:
                value=self.api.call('delivery','POST','/couriers',{'name':'Courier '+name,'zone':zone},key='public-courier:'+digest+name)
                fleet['couriers'].append(value['courier']['courier_id'])
        with self.state.connection() as c:
            c.execute('BEGIN IMMEDIATE');c.execute('INSERT INTO web_restaurant_fleets VALUES(?,?) ON CONFLICT(restaurant_id) DO NOTHING',(rid,json.dumps(fleet)))
            fleet=json.loads(c.execute('SELECT data FROM web_restaurant_fleets WHERE restaurant_id=?',(rid,)).fetchone()['data'])
            data=json.loads(c.execute('SELECT data FROM workspaces WHERE id=?',(wid,)).fetchone()['data']);data.update(fleet,restaurant_id=rid);c.execute('UPDATE workspaces SET data=? WHERE id=?',(json.dumps(data),wid))
    def context(self,sid):
        with self.state.connection() as c:row=c.execute('SELECT data FROM sessions WHERE id=?',(sid,)).fetchone()
        return json.loads(row['data'])
    def rotate(self,sid,identity,context=None,*,adopt_owner=None,new_account=None,expected_context=None,allow_pending_operator=False):
        if self.state.pending(sid,'checkout') and not allow_pending_operator:raise Conflict('Resolve the pending checkout before changing your sign-in session.')
        data=self.context(sid) if context is None else context
        new_sid,csrf=secrets.token_urlsafe(32),secrets.token_urlsafe(32)
        with self.state.connection() as c:
            c.execute('BEGIN IMMEDIATE')
            current=c.execute('SELECT data FROM sessions WHERE id=?',(sid,)).fetchone()
            if not current or (self.state._pending_checkout(c,sid) and not allow_pending_operator):raise Conflict('Your session changed or checkout is pending. Refresh before signing in.')
            saved=json.loads(current['data'])
            if expected_context is not None and saved!=expected_context:raise Conflict('Your cart changed during sign-in. Please try again.')
            if context is None:data=saved
            if context is not None and data.get('cart',{}).get('restaurant_id') and data.get('workspace_id'):
                source=c.execute('SELECT data FROM workspaces WHERE id=?',(saved.get('workspace_id'),)).fetchone()
                target=c.execute('SELECT data FROM workspaces WHERE id=?',(data['workspace_id'],)).fetchone()
                if source and target:
                    origin=json.loads(source['data']);destination=json.loads(target['data'])
                    if origin.get('restaurant_id')==data['cart']['restaurant_id']:
                        destination.update({k:origin[k] for k in ['restaurant_id','zone','couriers','run_id']});c.execute('UPDATE workspaces SET data=? WHERE id=?',(json.dumps(destination),destination['id']))
            if new_account:c.execute('INSERT INTO web_accounts VALUES(?,?,?,?,?,?)',new_account)
            if adopt_owner:c.execute('UPDATE web_workspace_owners SET owner=? WHERE owner=?',(identity['owner'],adopt_owner))
            c.execute('INSERT INTO sessions VALUES(?,?,?,?)',(new_sid,csrf,json.dumps(data),time.time()))
            c.execute('INSERT INTO web_auth VALUES(?,?,?,?,?)',(new_sid,identity['owner'],identity.get('account_id'),identity['role'],time.time()+(7200 if identity['role']=='operator' else 12*3600)))
            c.execute('UPDATE operations SET session_id=? WHERE session_id=?',(new_sid,sid))
            c.execute('DELETE FROM web_auth WHERE session_id=?',(sid,));c.execute('DELETE FROM sessions WHERE id=?',(sid,))
        return new_sid,csrf,data,self.identity(new_sid)
    @staticmethod
    def credentials(body,signup=False):
        required={'email','password','name'} if signup else {'email','password'}
        if not isinstance(body,dict) or set(body)!=required:raise BadRequest('Use only the fields shown in this form.')
        email=body['email'];password=body['password']
        if not isinstance(email,str) or len(email)>254 or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+',email.strip()):raise BadRequest('Enter a valid email address.')
        if not isinstance(password,str) or not 1<=len(password)<=128:raise BadRequest('Enter a password of at most 128 characters.')
        if signup and len(password)<15:raise BadRequest('Choose a passphrase of at least 15 characters.')
        if signup and (not isinstance(body['name'],str) or not 1<=len(body['name'].strip())<=100 or any(ord(x)<32 for x in body['name'])):raise BadRequest('Enter a name of 1 to 100 characters.')
        return email.strip().casefold(),password
    def signup(self,sid,identity,body):
        email,password=self.credentials(body,True)
        if self.state.pending(sid,'checkout'):raise Conflict('Resolve the pending checkout before creating an account.')
        if identity['role']!='guest':raise Conflict('Sign out before creating another account.')
        self.limit('signup-ip',request.remote_addr or 'unknown',8,3600)
        with self.state.connection() as c:exists=c.execute('SELECT 1 FROM web_accounts WHERE email=?',(email,)).fetchone()
        if exists:raise Conflict('An account could not be created with these details. Try signing in.')
        w=self.guest(sid,identity);name=body['name'].strip()
        try:self.api.call('customer','PATCH','/customers/'+str(w['customer_id']),{'name':name,'email':email})
        except Exception:
            # A lost edit response is accepted only after its actual committed result is read.
            actual=self.api.call('customer','GET','/customers/'+str(w['customer_id']))['customer']
            if actual.get('name')!=name or actual.get('email')!=email:raise Conflict('Your profile could not be confirmed. Review the details and try again.') from None
        account=str(uuid.uuid4())
        with password_work():hashed=generate_password_hash(password,method='scrypt')
        try:
            return self.rotate(sid,{'owner':account,'account_id':account,'role':'customer'},adopt_owner=identity['owner'],new_account=(account,email,hashed,name,w['id'],time.time()))
        except sqlite3.IntegrityError:raise Conflict('An account could not be created with these details. Try signing in.') from None
    def login(self,sid,identity,body):
        email,password=self.credentials(body)
        if self.state.pending(sid,'checkout'):raise Conflict('Resolve the pending checkout before signing in.')
        self.limit('login-ip',request.remote_addr or 'unknown',30,900);self.limit('login-email',email,8,900)
        with self.state.connection() as c:row=c.execute('SELECT * FROM web_accounts WHERE email=?',(email,)).fetchone()
        with password_work():valid=check_password_hash(row['password_hash'] if row else self.dummy,password)
        if not valid or not row:raise Unauthorized('Email or password was not recognised.')
        if identity['role']!='guest':raise Conflict('Sign out before changing accounts.')
        context=self.context(sid);guest_cart=context.get('cart',{});home=self.state.workspace(row['home_workspace'])
        if not home or not self.owns(row['id'],home['id']):raise Conflict('Your saved account is unavailable. Please contact the demo operator.')
        # Do not overwrite another session's unconfirmed order or active cart.
        with self.state.connection() as c:
            sessions=c.execute('SELECT s.id,s.data FROM sessions s JOIN web_auth a ON a.session_id=s.id WHERE a.account_id=?',(row['id'],)).fetchall()
        if guest_cart.get('items') and any(self.state.pending(s['id'],'checkout') for s in sessions):raise Conflict('Finish the pending checkout in your other signed-in session first.')
        return self.rotate(sid,{'owner':row['id'],'account_id':row['id'],'role':'customer'},{'workspace_id':home['id'],'cart':guest_cart},adopt_owner=identity['owner'],expected_context=context)
    def public_identity(self,identity):
        result={'public_access':True,'role':identity['role'],'signed_in':identity['role']!='guest','name':None,'email':None}
        if identity.get('account_id'):
            with self.state.connection() as c:row=c.execute('SELECT name,email FROM web_accounts WHERE id=?',(identity['account_id'],)).fetchone()
            if row:result.update(name=row['name'],email=row['email'])
        return result
