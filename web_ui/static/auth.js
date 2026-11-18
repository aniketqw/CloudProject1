import {api,$,toast} from './core.js';
export function auth(){
 const form=$('#auth-form');if(!form||form.dataset.bound)return;
 form.dataset.bound='true';
 form.addEventListener('submit',async event=>{
  event.preventDefault();if(form.dataset.submitting)return;
  form.dataset.submitting='true';const button=form.querySelector('button[type="submit"]'),values=Object.fromEntries(new FormData(form)),mode=form.dataset.mode;
  button.disabled=true;$('#auth-error').textContent='';
  try{await api('/api/auth/'+(mode==='signup'?'signup':mode==='staff'?'staff':'signin'),{method:'POST',body:values});location.assign(mode==='staff'?'/operations':'/');}
  catch(error){$('#auth-error').textContent=error.message;toast(error.message,true);}
  finally{form.elements.password.value='';delete form.dataset.submitting;button.disabled=false;}
 });
 form.querySelector('button[type="submit"]').disabled=false;
}
