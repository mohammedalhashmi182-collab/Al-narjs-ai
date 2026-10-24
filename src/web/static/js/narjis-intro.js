/* First-visit intro for the home page. Adapted from the approved intro.js:
   plays once (localStorage), skippable, auto-dismisses at ~3s, no video. */
(function(){
var KEY='nj-intro-seen';
var box=document.getElementById('njIntro');
if(!box||!document.documentElement.classList.contains('nj-intro-on'))return;
try{localStorage.setItem(KEY,'1')}catch(e){}
var ICONS={
bot:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5h16v11H9l-5 4z"/><circle cx="9.5" cy="10.5" r="1" fill="currentColor"/><circle cx="14.5" cy="10.5" r="1" fill="currentColor"/></svg>',
gears:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="9" cy="10" r="3"/><path d="M9 3v2M9 15v2M2 10h2M14 10h2M4 5l1.5 1.5M12.5 13.5L14 15M4 15l1.5-1.5M12.5 6.5L14 5"/><circle cx="17.5" cy="17.5" r="2"/><path d="M17.5 13.5v1M17.5 20.5v1M13.5 17.5h1M20.5 17.5h1"/></svg>',
agent:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 2l2.4 5.6L20 10l-5.6 2.4L12 18l-2.4-5.6L4 10l5.6-2.4z"/><path d="M19 17l.8 2 2 .8-2 .8-.8 2-.8-2-2-.8 2-.8z"/></svg>',
pen:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"><path d="M12 3l7 7-7 11-7-11z"/><circle cx="12" cy="11" r="1.6"/><path d="M12 12.6V21"/></svg>',
doc:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"><path d="M6 2h8l5 5v15H6z"/><path d="M14 2v5h5M9 12h7M9 16h5"/></svg>',
chart:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21h18"/><path d="M6 17v-4M11 17V9M16 17v-6"/><path d="M4 9l6-5 4 3 6-4"/></svg>'};
var TILES=[["bot",.1,"iv",-12,82],["gears",.27,"",8,70],["agent",.44,"acc",-6,90],["pen",.6,"",14,66],["doc",.76,"iv",-10,78],["chart",.92,"acc",9,60]];
var root=box.querySelector('.nj-hero'),svg=root.querySelector('.nj-path'),p=svg.querySelector('.dots'),wrap=root.querySelector('.nj-tiles');
var L=p.getTotalLength(),els=[],gone=false,timer;
TILES.forEach(function(t,i){var d=document.createElement('div');d.className='nj-tile '+t[2];d.style.setProperty('--r',t[3]+'deg');d.style.setProperty('--s',t[4]+'px');d.style.setProperty('--fd',(-i*.8)+'s');d.innerHTML='<i>'+ICONS[t[0]]+'</i>';wrap.appendChild(d);els.push(d)});
function pos(f){var r=svg.getBoundingClientRect(),vb=svg.viewBox.baseVal,pt=p.getPointAtLength(L*f);return[pt.x/vb.width*r.width,pt.y/vb.height*r.height]}
function place(){els.forEach(function(el,i){var q=pos(TILES[i][1]);el.style.left=q[0]+'px';el.style.top=q[1]+'px'})}
function close(){
 if(gone)return;gone=true;clearTimeout(timer);
 removeEventListener('resize',place);document.removeEventListener('keydown',onKey);
 box.classList.add('out');
 setTimeout(function(){if(box.parentNode)box.parentNode.removeChild(box);document.documentElement.classList.remove('nj-intro-on')},400);
}
function onKey(e){if(e.key==='Escape')close()}
place();addEventListener('resize',place);
document.addEventListener('keydown',onKey);
box.querySelector('.nj-intro-skip').addEventListener('click',close);
root.classList.add('play');
if(els[0]&&els[0].animate)els.forEach(function(el,i){var f=TILES[i][1],a=pos(Math.max(0,f-.14)),b=pos(f);
 el.animate([{opacity:0,transform:'translate('+(a[0]-b[0])+'px,'+(a[1]-b[1])+'px) scale(.6) rotate(-20deg)'},{opacity:1,transform:'none'}],{duration:700,delay:1000+i*120,easing:'cubic-bezier(.2,.9,.25,1.15)',fill:'forwards'})});
timer=setTimeout(close,2700);
})();
