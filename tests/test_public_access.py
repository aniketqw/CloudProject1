"""Public/customer/staff boundary and real persistent-session regression contracts."""
import json,re,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
from werkzeug.security import generate_password_hash,check_password_hash
from web_ui.app import create_app
from web_ui.client import ServiceError
from test_web_ui import Backend

PASSWORD='a unique synthetic passphrase'
class AccountsBackend(Backend):
    def __init__(self):
        super().__init__();self.people={};self.addresses={};self.sequence=100;self.fleet_keys={};self.notes={}
    def call(self,service,method,path,body=None,*,key=None,version=None,query=None):
        if service=='customer':
            self.calls.append((service,method,path,body,key,version,query))
            parts=path.strip('/').split('/')
            if method=='POST' and path=='/customers':
                self.sequence+=1;self.people[self.sequence]={'id':self.sequence,**body};self.addresses[self.sequence]=[];return {'customer':self.people[self.sequence].copy()}
            cid=int(parts[1])
            if len(parts)>2 and parts[2]=='addresses':
                if method=='POST':self.sequence+=1;self.addresses[cid].append({'id':self.sequence,'customer_id':cid,**body})
                return {'addresses':self.addresses[cid].copy(),'address':self.addresses[cid][-1] if self.addresses[cid] else None}
            if method=='PATCH':self.people[cid].update(body)
            return {'customer':self.people[cid].copy()}
        if service=='delivery' and method=='POST' and path in ['/delivery/zones','/couriers']:
            self.calls.append((service,method,path,body,key,version,query))
            if key not in self.fleet_keys:self.fleet_keys[key]={'run_id':str(uuid.uuid4())} if path.endswith('zones') else {'courier':{'courier_id':str(uuid.uuid4())}}
            return self.fleet_keys[key]
        if service=='notification' and method=='GET':
            cid=(query or {}).get('customer_id');rows=[x for x in self.notes.values() if str(x['recipient_id'])==str(cid)]
            if path=='/notifications':return {'notifications':rows,'recipient_unread_count':sum(x['unread'] for x in rows),'next_after':None}
            note=self.notes.get(path.rsplit('/',1)[-1])
            if not note or str(note['recipient_id'])!=str(cid):raise ServiceError(404,'Notification is outside the recipient.')
            return {'notification':note}
        return super().call(service,method,path,body,key=key,version=version,query=query)

class PublicAccess(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.backend=AccountsBackend();self.staff_hash=generate_password_hash(PASSWORD)
        self.config={'TESTING':True,'APP_ENV':'local','PUBLIC_ACCESS':True,'STATE_PATH':str(Path(self.temp.name)/'web.sqlite3'),'STAFF_USER':'test-operator','STAFF_PASSWORD_HASH':self.staff_hash}
        self.app=create_app(self.config,client=self.backend);self.a=self.app.test_client();self.b=self.app.test_client()
    def tearDown(self):self.temp.cleanup()
    def csrf(self,client):return re.search('name="csrf-token" content="([^"]+)"',client.get('/').get_data(as_text=True)).group(1)
    def post(self,client,path,body):return client.post(path,json=body,headers={'X-CSRF-Token':self.csrf(client)})
    def guest(self,client):
        value=self.post(client,'/api/auth/guest',{});self.assertEqual(value.status_code,201,value.get_json());return value.get_json()['workspace']
    def cart(self,client):
        if not client.get('/api/context').get_json()['workspace']:self.guest(client)
        value=self.post(client,'/api/cart',{'restaurant_id':'paper','item_id':'bowl','quantity':1});self.assertEqual(value.status_code,200,value.get_json())
    def order(self,client):
        self.cart(client);cid=client.get('/api/profile').get_json()['customer']['id'];op=str(uuid.uuid4());value=self.post(client,'/api/checkout',{'operation_id':op,'address_id':9});self.assertEqual(value.status_code,201,value.get_json());return value.get_json()['order']['order_id']
    def signup(self,client,email='one@example.test'):
        value=self.post(client,'/api/auth/signup',{'name':'Synthetic diner','email':email,'password':PASSWORD});self.assertEqual(value.status_code,200,value.get_json());return value.get_json()
    def signin(self,client,email='one@example.test'):return self.post(client,'/api/auth/signin',{'email':email,'password':PASSWORD})
    def test_public_browsing_does_not_require_login_or_create_backend_records(self):
        response=self.a.get('/');self.assertEqual(response.status_code,200);self.assertNotIn('WWW-Authenticate',response.headers)
        html=response.get_data(as_text=True);self.assertIn('href="/signin"',html);self.assertNotIn('href="/kitchen"',html);self.assertNotIn('href="/operations"',html)
        self.assertEqual(self.a.get('/api/restaurants').status_code,200);self.assertEqual(self.a.get('/api/restaurants/paper/menu').status_code,200);self.assertFalse(self.backend.people)
    def test_guest_checkouts_and_workspace_ids_are_isolated(self):
        wa=self.guest(self.a);wb=self.guest(self.b);self.assertNotEqual(wa['customer_id'],wb['customer_id'])
        oid=self.order(self.a);self.assertEqual(self.b.get('/api/orders/'+oid).status_code,404)
        self.assertEqual(self.post(self.b,'/api/context',{'workspace_id':wa['id']}).status_code,404)
        self.assertEqual(self.a.get('/api/orders').get_json()['orders'][0]['order_id'],oid);self.assertEqual(self.b.get('/api/orders').get_json()['orders'],[])
        self.assertEqual([x['id'] for x in self.a.get('/api/workspaces').get_json()['workspaces']],[wa['id']])
    def test_staff_routes_and_role_escalation_are_blocked_before_backend_actions(self):
        self.guest(self.a);before=len(self.backend.calls)
        for path in ['/api/kitchen','/api/kitchen/menu','/api/courier','/api/fleet','/api/operations','/api/operations/stream','/api/system','/api/notifications?recipient=courier']:
            self.assertEqual(self.a.get(path).status_code,403,path)
        self.assertEqual(self.post(self.a,'/api/workspaces',{}).status_code,403)
        self.assertEqual(self.post(self.a,'/api/context',{'restaurant_id':'paper'}).status_code,403)
        self.assertEqual(len(self.backend.calls),before)
        self.assertEqual(self.a.get('/kitchen').status_code,302)
        self.assertEqual(self.post(self.a,'/api/auth/signup',{'name':'Demo','email':'new@example.test','password':PASSWORD,'role':'operator'}).status_code,400)
    def test_signup_rotates_cookie_and_csrf_and_stores_only_password_hash(self):
        old_csrf=self.csrf(self.a);old_cookie=self.a.get_cookie('supper_session').value;self.cart(self.a);ctx=self.signup(self.a)
        self.assertEqual(ctx['auth']['role'],'customer');self.assertNotEqual(self.a.get_cookie('supper_session').value,old_cookie);self.assertNotEqual(self.csrf(self.a),old_csrf)
        state=self.app.extensions['web_state']
        with state.connection() as c:
            row=c.execute('SELECT * FROM web_accounts').fetchone();self.assertTrue(check_password_hash(row['password_hash'],PASSWORD));self.assertNotIn(PASSWORD,row['password_hash']);self.assertFalse(c.execute('SELECT 1 FROM sessions WHERE id=?',(old_cookie,)).fetchone());self.assertNotIn(PASSWORD,str([dict(r) for r in c.execute('SELECT * FROM operations')]))
        self.assertNotIn('password_hash',json.dumps(ctx));self.assertEqual(len(self.a.get('/api/cart').get_json()['items']),1)
    def test_returning_customer_recovers_profile_addresses_and_history(self):
        self.signup(self.a);self.post(self.a,'/api/addresses',{'operation_id':str(uuid.uuid4()),'action':'add','address':{'label':'Demo','line1':'Fictional lane','city':'Demo','postal_code':'000000','country_code':'IN','is_default':True}});oid=self.order(self.a)
        self.assertEqual(self.signin(self.b).status_code,200);self.assertEqual(self.b.get('/api/profile').get_json()['customer']['email'],'one@example.test');self.assertEqual(len(self.b.get('/api/profile').get_json()['addresses']),1);self.assertEqual(self.b.get('/api/orders/'+oid).status_code,200)
    def test_guest_cart_and_prior_guest_orders_transfer_only_after_valid_signin(self):
        self.signup(self.a);home=self.a.get('/api/context').get_json()['workspace']['id'];guest_oid=self.order(self.b);self.cart(self.b)
        bad=self.post(self.b,'/api/auth/signin',{'email':'one@example.test','password':'wrong'});self.assertEqual(bad.status_code,401);self.assertEqual(self.a.get('/api/orders/'+guest_oid).status_code,404)
        self.assertEqual(self.signin(self.b).status_code,200);self.assertEqual(self.b.get('/api/context').get_json()['workspace']['id'],home);self.assertEqual(len(self.b.get('/api/cart').get_json()['items']),1);self.assertEqual(self.b.get('/api/orders/'+guest_oid).status_code,200)
    def test_signout_invalidates_old_cookie_and_protects_order_history(self):
        self.signup(self.a);oid=self.order(self.a);old=self.a.get_cookie('supper_session').value
        self.assertEqual(self.post(self.a,'/api/auth/signout',{}).status_code,200);self.assertFalse(self.a.get('/api/context').get_json()['auth']['signed_in'])
        self.b.set_cookie('supper_session',old);self.b.get('/');self.assertEqual(self.b.get('/api/orders').get_json()['orders'],[]);self.assertEqual(self.b.get('/api/orders/'+oid).status_code,409)
    def test_unknown_checkout_blocks_auth_changes_and_retries_same_order(self):
        self.cart(self.a);self.backend.lost=True;op=str(uuid.uuid4());body={'operation_id':op,'address_id':9}
        self.assertEqual(self.post(self.a,'/api/checkout',body).status_code,503)
        self.assertEqual(self.post(self.a,'/api/auth/signup',{'name':'Demo','email':'one@example.test','password':PASSWORD}).status_code,409)
        self.assertEqual(self.post(self.a,'/api/auth/signout',{}).status_code,409)
        self.assertEqual(self.post(self.a,'/api/checkout',body).status_code,201);self.assertEqual(len(self.backend.orders),1)
    def test_login_csrf_and_old_csrf_cannot_change_sessions(self):
        self.assertEqual(self.a.post('/api/auth/signup',json={'name':'Demo','email':'one@example.test','password':PASSWORD}).status_code,400)
        old=self.csrf(self.a);self.signup(self.a);self.assertEqual(self.a.post('/api/auth/signout',json={},headers={'X-CSRF-Token':old}).status_code,400)
    def test_staff_form_uses_separate_credentials_and_rotates_session(self):
        self.guest(self.a);old=self.a.get_cookie('supper_session').value
        self.assertEqual(self.post(self.a,'/api/auth/staff',{'username':'test-operator','password':PASSWORD}).status_code,200);self.assertNotEqual(self.a.get_cookie('supper_session').value,old);self.assertEqual(self.a.get('/api/system').status_code,200);self.assertIn('href="/kitchen"',self.a.get('/').get_data(as_text=True))
    def test_legacy_workspaces_do_not_become_public(self):
        state=self.app.extensions['web_state'];wid=str(uuid.uuid4());state.save_workspace({'id':wid,'status':'READY','customer_id':7,'name':'Private operator fixture','couriers':[],'orders':[]})
        self.assertEqual(self.a.get('/api/workspaces').get_json()['workspaces'],[]);self.assertEqual(self.post(self.a,'/api/context',{'workspace_id':wid}).status_code,404)
    def test_authentication_rate_limit_is_persisted_and_does_not_echo_password(self):
        for _ in range(8):self.assertEqual(self.post(self.a,'/api/auth/signin',{'email':'missing@example.test','password':PASSWORD}).status_code,401)
        value=self.post(self.a,'/api/auth/signin',{'email':'missing@example.test','password':PASSWORD});self.assertEqual(value.status_code,429);self.assertNotIn(PASSWORD,value.get_data(as_text=True))
    def test_restaurant_fleet_is_shared_not_recreated_per_customer(self):
        self.cart(self.a);self.cart(self.b);self.assertEqual(len(self.backend.fleet_keys),3);self.assertNotIn('couriers',self.a.get('/api/context').get_json()['workspace'])
    def test_accounts_and_ownership_survive_app_recreation(self):
        self.signup(self.a);oid=self.order(self.a);self.app=create_app(self.config,client=self.backend);other=self.app.test_client();self.assertEqual(self.signin(other).status_code,200);self.assertEqual(other.get('/api/orders/'+oid).status_code,200)
    def test_two_signed_in_customers_cannot_read_or_change_each_others_records(self):
        self.signup(self.a);self.signup(self.b,'two@example.test');oid=self.order(self.a)
        self.assertEqual(self.b.get('/api/orders/'+oid).status_code,404);self.assertEqual(self.b.get('/api/profile').get_json()['customer']['email'],'two@example.test')
        value=self.post(self.b,'/api/orders/'+oid+'/payment',{'operation_id':str(uuid.uuid4()),'action':'pay','expected_version':1});self.assertEqual(value.status_code,404)
    def test_customer_inbox_and_read_commands_use_owned_recipient_ids(self):
        self.signup(self.a);self.signup(self.b,'two@example.test');cid=self.a.get('/api/profile').get_json()['customer']['id'];note=str(uuid.uuid4())
        self.backend.notes[note]={'notification_id':note,'recipient_id':cid,'recipient_type':'customer','created_at':'2026-11-18T00:00:00Z','unread':True,'state':'SENT'}
        self.assertEqual(len(self.a.get('/api/notifications').get_json()['notifications']),1);self.assertEqual(self.b.get('/api/notifications').get_json()['notifications'],[])
        payload={'operation_id':str(uuid.uuid4()),'action':'read','expected_version':1}
        self.assertEqual(self.post(self.b,'/api/notifications/'+note+'/actions',payload).status_code,404);self.assertEqual(self.post(self.a,'/api/notifications/'+note+'/actions',payload).status_code,200)
    def test_expired_account_session_does_not_retain_customer_access(self):
        self.signup(self.a);self.order(self.a);sid=self.a.get_cookie('supper_session').value
        with self.app.extensions['web_state'].connection() as c:c.execute('UPDATE web_auth SET expires=0 WHERE session_id=?',(sid,))
        self.assertFalse(self.a.get('/api/context').get_json()['auth']['signed_in']);self.assertEqual(self.a.get('/api/orders').get_json()['orders'],[])
    def test_profile_or_staff_role_cannot_be_selected_in_customer_context(self):
        self.signup(self.a)
        self.assertEqual(self.post(self.a,'/api/context',{'owner':'other','role':'operator'}).status_code,400)
        self.assertEqual(self.post(self.a,'/api/auth/staff',{'username':'δοκιμή','password':PASSWORD}).status_code,401)
    def test_cloud_customer_home_is_public_but_legacy_cloud_gate_remains_available(self):
        with patch.dict('os.environ',{'WEB_PUBLIC_ORIGIN':'https://demo.example.test','WEB_OPERATOR_USER':'test-operator','WEB_OPERATOR_PASSWORD_HASH':self.staff_hash}):
            cfg={**self.config,'APP_ENV':'cloud'};app=create_app(cfg,client=self.backend);c=app.test_client();value=c.get('/',base_url='https://demo.example.test');self.assertEqual(value.status_code,200);self.assertNotIn('WWW-Authenticate',value.headers);self.assertIn('Secure',value.headers['Set-Cookie'])
            app=create_app({**cfg,'PUBLIC_ACCESS':False},client=self.backend);self.assertEqual(app.test_client().get('/',base_url='https://demo.example.test').status_code,401)
if __name__=='__main__':unittest.main()
