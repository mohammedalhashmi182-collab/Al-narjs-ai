(function(){
  const input=document.getElementById('kChatInput');const send=document.getElementById('kSendBtn');const msgs=document.getElementById('kChatMessages');const welcome=document.getElementById('kWelcome');
  function autoGrow(){if(!input)return;input.style.height='44px';input.style.height=Math.min(input.scrollHeight,220)+'px';}
  function addMsg(role,text){if(welcome)welcome.remove();const m=document.createElement('div');m.className='k-message '+(role==='user'?'user':'assistant');const b=document.createElement('div');b.className='k-message-content';b.textContent=text;m.appendChild(b);msgs.appendChild(m);msgs.scrollTop=msgs.scrollHeight;}
  async function sendMsg(){const v=input.value.trim();if(!v)return;addMsg('user',v);input.value='';autoGrow();send.disabled=true;addMsg('assistant','...');try{const r=await fetch('/api/v1/karmish/talk',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:v})});const d=await r.json();msgs.lastChild.remove();addMsg('assistant',d.reply||'تم الاستلام.');}catch(e){msgs.lastChild.remove();addMsg('assistant','حدث خطأ في الاتصال.');}send.disabled=false;input.focus();}
  if(input){input.addEventListener('input',autoGrow);input.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendMsg();}});}
  if(send){send.addEventListener('click',sendMsg);}
  autoGrow();
})();
