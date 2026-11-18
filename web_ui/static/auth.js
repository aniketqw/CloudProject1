import {api,$,toast} from './core.js';
export async function auth(ctx){
 const form=$('#auth-form');if(!form)return;
 form.addEventListener('submit',async event=>{
  event.preventDefault();const button=form.querySelector('button[type="submit"]'),values=Object.fromEntries(new FormData(form)),mode=form.dataset.mode;
  button.disabled=true;$('#auth-error').textContent='';
  try{await api('/api/auth/'+(mode==='signup'?'signup':mode==='staff'?'staff':'signin'),{method:'POST',body:values});location.assign(mode==='staff'?'/operations':'/');}
  catch(error){$('#auth-error').textContent=error.message;toast(error.message,true);}
  finally{form.elements.password.value='';button.disabled=false;}
 });
}
