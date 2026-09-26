'use strict';
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {token: sessionStorage.getItem('iyi-token'), user: null, mood: null, expectations: new Set(), step: 1, specialties: [], profile: null, selectedSlot: null, authMode: 'login', reviewTherapist: null};
const days = ['Pazartesi','Salı','Çarşamba','Perşembe','Cuma','Cumartesi','Pazar'];
const moods = {iyi:'İyi hissediyorum',karisik:'Biraz karışık',kaygili:'Kaygılıyım',uzgun:'Üzgünüm',yorgun:'Yorgunum'};
const statuses = {pending:'Onay bekliyor',confirmed:'Onaylandı',cancelled:'İptal edildi',completed:'Tamamlandı'};
const money = v => new Intl.NumberFormat('tr-TR',{style:'currency',currency:'TRY',maximumFractionDigits:2}).format(v);
const dateLabel = v => new Intl.DateTimeFormat('tr-TR',{dateStyle:'long',timeStyle:'short',timeZone:'Europe/Istanbul'}).format(new Date(v));
const localDate = (d=new Date()) => new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/Istanbul',year:'numeric',month:'2-digit',day:'2-digit'}).format(d);
const timeLabel = v => new Intl.DateTimeFormat('tr-TR',{hour:'2-digit',minute:'2-digit',timeZone:'Europe/Istanbul'}).format(new Date(v));
const initials = name => name.split(' ').filter(Boolean).slice(0,2).map(x=>x[0]).join('');
async function api(path, options={}) {
  let response;
  try { response = await fetch(path,{...options,headers:{'Content-Type':'application/json',...(state.token?{Authorization:`Bearer ${state.token}`} : {}),...options.headers}}); }
  catch { throw new Error('Bağlantı kurulamadı. İnternet bağlantını kontrol edip tekrar dene.'); }
  if (response.status === 204) return null;
  const data = await response.json().catch(()=>({}));
  if (!response.ok) {
    if (response.status===401 && path!=='/login') { logout(false); }
    let message = Array.isArray(data.detail) ? data.detail.map(x=>`${x.loc.slice(1).join(' / ')}: ${x.msg}`).join('\n') : data.detail;
    if (response.status >= 500) message='İşlem şu anda tamamlanamadı. Lütfen biraz sonra tekrar dene.';
    const err = new Error(message || 'İşlem tamamlanamadı.'); err.status=response.status; throw err;
  }
  return data;
}
function message(form, text, success=false) { const el=form.querySelector('.form-message'); el.textContent=text; el.classList.toggle('success',success); }
function toast(text) { $('#toast').textContent=text; $('#toast').hidden=false; clearTimeout(state.toastTimer); state.toastTimer=setTimeout(()=>$('#toast').hidden=true,4500); }
function setBusy(form, busy) { form.querySelectorAll('button[type=submit]').forEach(x=>x.disabled=busy); }
function showAuth(mode='login') { state.authMode=mode; updateAuth(); $('#auth-dialog').showModal(); }
function updateAuth() {
  const register=state.authMode==='register'; $('#register-fields').hidden=!register;
  $('#auth-form').elements.full_name.required=register;
  $('#auth-heading').textContent=register?'Kendin için bir adım.':'Tekrar hoş geldin.';
  $('#auth-submit').textContent=register?'Hesap oluştur →':'Giriş yap →';
  $('#auth-toggle').textContent=register?'Zaten hesabın var mı? Giriş yap':'Hesabın yok mu? Kayıt ol';
  $('#auth-form').elements.password.autocomplete=register?'new-password':'current-password';
  message($('#auth-form'),'');
}
function renderAccount() {
  $('#account-nav').innerHTML=state.user?`<button class="text-button account-name" data-action="dashboard">${esc(state.user.full_name.split(' ')[0])} · Hesabım</button><button class="text-button" data-action="logout">Çıkış</button>`:'<button class="login" data-action="login">Giriş yap <span>↗</span></button>';
}
function logout(notify=true) { state.token=null;state.user=null;sessionStorage.removeItem('iyi-token');renderAccount();showHome();if(notify)toast('Güvenli bir şekilde çıkış yaptın.'); }
function showHome() { $('#discover-view').hidden=false;$('#dashboard-view').hidden=true; }
function checkboxOptions(selected=[]) { $('#profile-specialties').innerHTML=state.specialties.map((x,i)=>`<label><input type="checkbox" name="specialty" value="${esc(x)}" ${selected.includes(x)?'checked':''}>${esc(x)}</label>`).join(''); }
function renderStep() {
  const second=state.step===2;$('#mood-step').hidden=second;$('#expectation-step').hidden=!second;$('#back-step').hidden=!second;
  $('#step-label').textContent=second?'02 / 02 · İHTİYACINA ALAN AÇ':'01 / 02 · SENİ DİNLEYELİM';
  $('#checkin-heading').textContent=second?'Bu yolculuktan beklentin ne?':'Bugün nasıl hissediyorsun?';
  $('#step-description').textContent=second?'Hangi alanlarda destek almak istersin? Birlikte keşfedelim.':'Doğru ya da yanlış bir cevap yok. Sana en yakın olanı seç.';
  $('#step-dot').classList.toggle('current',second);
  $('#next-step').innerHTML=second?'Bana uygun uzmanları göster <span>→</span>':'Devam edelim <span>→</span>';
  $('#next-step').disabled=second?state.expectations.size===0:!state.mood;
}
async function loadTherapists(personalized=false) {
  showHome(); $('#results').hidden=false;$('#therapist-list').innerHTML='<p class="loading">Uzmanlar yükleniyor…</p>';
  const params=new URLSearchParams(); if(personalized){if(state.mood)params.set('mood',state.mood);state.expectations.forEach(x=>params.append('expectations',x));}
  $('#results-title').textContent=personalized?'İhtiyacına alan açan uzmanlar':'Tanışabileceğin uzmanlar';
  $('#results-description').textContent=personalized?'Seçimlerinle kesişen çalışma alanlarına göre listelendi. Sana yakın gelen uzmanı tanı.':'Çalışma alanlarını incele, sana uygun zamanı seç.';
  $('#results').scrollIntoView({behavior:'smooth',block:'start'});
  const requestId=++state.resultsRequest || (state.resultsRequest=1);
  try {
    const list=await api('/api/therapists?'+params);
    if(requestId!==state.resultsRequest)return;
    $('#therapist-list').innerHTML=list.length?list.map(p=>`<article class="therapist-card"><div class="card-top"><div class="avatar">${esc(initials(p.full_name))}</div><div><h3>${esc(p.full_name)}</h3><p>${esc(p.title)}</p><span class="verified">✓ Doğrulanmış profil</span></div></div><div class="rating">${p.rating?'★ '+p.rating.toFixed(1)+' · '+p.review_count+' değerlendirme':'Henüz değerlendirme yok'}</div><div class="tags">${p.specialties.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}</div><p class="card-bio">${esc((p.bio||'Uzmanın profilini ve eğitim bilgilerini inceleyebilirsin.').slice(0,155))}</p>${p.match_reasons.length?`<span class="match">Seçiminle örtüşen: ${esc(p.match_reasons.join(', '))}</span>`:''}<div class="card-bottom"><span class="price">${money(p.session_price)} <small>/ ${p.session_minutes} dk</small></span><button class="text-button" data-profile="${p.id}">Tanışalım ↗</button></div></article>`).join(''):`<div class="empty"><h3>${personalized?'Bu seçimler için henüz uzman yok.':'Yeni tanışmalar için hazırlanıyoruz.'}</h3><p>${personalized?'Seçimlerini değiştirebilir veya tüm uzmanları inceleyebilirsin.':'Doğrulanmış uzmanlar, çalışma alanları ve müsait saatleriyle burada listelenecek.'}</p><button class="text-button" data-action="${personalized?'browse':'register-therapist'}">${personalized?'Tüm uzmanları göster →':'Uzman olarak katıl →'}</button></div>`;
  } catch(e) {if(requestId===state.resultsRequest)$('#therapist-list').innerHTML=`<div class="empty error-state"><p>${esc(e.message)}</p><button class="text-button" data-action="browse">Tekrar dene</button></div>`;}
}
async function openProfile(id) {
  const dialog=$('#profile-dialog'); $('#profile-content').innerHTML='<p class="loading">Uzman profili yükleniyor…</p>'; if(!dialog.open)dialog.showModal();state.selectedSlot=null;
  const requestId=++state.profileRequest || (state.profileRequest=1);
  try {
    const [p,reviews]=await Promise.all([api('/api/therapists/'+id),api('/api/therapists/'+id+'/reviews')]);
    if(requestId!==state.profileRequest)return;state.profile=p;
    $('#profile-content').innerHTML=`<div class="detail-head"><div class="avatar">${esc(initials(p.full_name))}</div><div><span class="verified">✓ Doğrulanmış profil</span><h2>${esc(p.full_name)}</h2><p>${esc(p.title)}</p></div></div><div class="detail-columns"><section><div class="tags">${p.specialties.map(x=>`<span class="tag">${esc(x)}</span>`).join('')}</div><h3>Tanışalım</h3><p style="white-space:pre-wrap">${esc(p.bio||'Henüz tanıtım yazısı eklenmedi.')}</p><h3>Eğitim</h3>${p.education.length?'<ul>'+p.education.map(x=>`<li>${esc(x)}</li>`).join('')+'</ul>':'<p>Henüz eğitim bilgisi eklenmedi.</p>'}<h3>Danışan deneyimleri</h3><p class="rating">${p.rating?'★ '+p.rating.toFixed(1)+' · '+p.review_count+' değerlendirme':'İlk değerlendirme henüz paylaşılmadı.'}</p>${reviews.map(r=>`<article class="review-item"><span class="rating">${'★'.repeat(r.rating)}${'☆'.repeat(5-r.rating)}</span><p>${esc(r.comment||'Yazılı yorum eklenmedi.')}</p><span class="small">Seansını tamamlamış danışan · ${esc(new Date(r.created_at).toLocaleDateString('tr-TR'))}</span></article>`).join('')}</section><section class="booking-box"><span class="step-label">KENDİNE ZAMAN AYIR</span><h3 style="margin-top:8px">Birlikte başlayalım.</h3><div class="price">${money(p.session_price)} <small>/ ${p.session_minutes} dakika</small></div><label>Seans günü<input id="booking-date" type="date" value="${localDate()}" min="${localDate()}" max="${localDate(new Date(Date.now()+90*86400000))}"></label><p class="small">Tüm saatler Türkiye saatidir.</p><div id="slots" class="slots" aria-live="polite"></div><label class="check-label"><input type="checkbox" id="share-intake"><span>Duygu ve beklenti seçimlerimi bu uzmanla paylaşmak istiyorum.</span></label><p class="small">${state.mood?esc(moods[state.mood])+' · '+esc([...state.expectations].join(', ')):'Henüz duygu veya beklenti seçmedin.'}</p><button class="primary full" id="book-button" disabled>Randevu talebi oluştur →</button><p id="booking-message" class="form-message" role="status"></p><p class="small">Uzman onayından sonra randevun kesinleşir. Bu adımda ödeme alınmaz.</p></section></div>`;
    $('#booking-date').addEventListener('change',loadSlots);$('#book-button').addEventListener('click',book);await loadSlots();
  } catch(e) {$('#profile-content').innerHTML=`<p class="error-state">${esc(e.message)}</p>`;}
}
async function loadSlots() {
  const date=$('#booking-date').value,id=state.profile.id;state.selectedSlot=null;$('#book-button').disabled=true;
  $('#slots').innerHTML='<p class="small">Saatler yükleniyor…</p>';
  const requestId=++state.slotsRequest || (state.slotsRequest=1);
  try {const data=await api(`/api/therapists/${id}/slots?date=${date}`);if(requestId!==state.slotsRequest)return;
    $('#slots').innerHTML=data.slots.length?data.slots.map(x=>`<button class="slot" aria-pressed="false" data-slot="${esc(x)}">${timeLabel(x)}</button>`).join(''):'<p class="small" style="grid-column:1/-1">Bu gün için açık saat yok. Başka bir gün seçebilirsin.</p>';
  }catch(e){if(requestId===state.slotsRequest)$('#slots').innerHTML=`<p class="small error-state" style="grid-column:1/-1">${esc(e.message)}</p>`;}
}
async function book() {
  if(!state.user){$('#profile-dialog').close();showAuth();toast('Randevu için giriş yap. Ardından uzman profilinden saati tekrar seçebilirsin.');return;}
  if(!state.selectedSlot)return;const button=$('#book-button');button.disabled=true;
  const share=$('#share-intake').checked;
  try {await api('/api/appointments',{method:'POST',body:JSON.stringify({therapist_id:state.profile.id,date:$('#booking-date').value,start_time:timeLabel(state.selectedSlot),mood:share?state.mood:null,expectations:share?[...state.expectations]:[]})});$('#profile-dialog').close();toast('Randevu talebin uzmana iletildi.');await showDashboard();}
  catch(e){$('#booking-message').textContent=e.message;await loadSlots();}
}
async function showDashboard() {
  if(!state.user){showAuth();return;}$('#discover-view').hidden=true;$('#dashboard-view').hidden=false;
  const therapist=state.user.role==='therapist';$('#therapist-settings').hidden=!therapist;
  $('#dashboard-title').textContent=therapist?'Uzman çalışma alanım':'Randevularım';
  $('#dashboard-description').textContent=`Merhaba ${state.user.full_name.split(' ')[0]}. ${therapist?'Profilini, çalışma saatlerini ve randevularını buradan yönet.':'Sana ayırdığın zamanları buradan takip edebilirsin.'}`;
  $('#appointments-list').innerHTML='<p class="loading">Randevular yükleniyor…</p>';
  if(therapist){
    const form=$('#profile-form');form.reset();checkboxOptions();
    try {const p=await api('/api/therapists/me');for(const name of ['title','bio','license_no','session_minutes','session_price'])form.elements[name].value=p[name]??'';form.elements.education.value=p.education.join('\n');checkboxOptions(p.specialties);$('#verification-state').textContent=p.is_verified?'✓ Profilin doğrulanmış ve uzman listesinde görünüyor.':'Profilin doğrulama bekliyor. Doğrulandıktan sonra danışanlar seni görebilecek.';await loadAvailability();}
    catch(e){$('#verification-state').textContent=e.status===404?'Profilini oluştur, ardından çalışma saatlerini ekle.':e.message;$('#availability-list').textContent='';}
  }
  await loadAppointments();
}
async function loadAvailability(){const list=await api('/api/therapists/me/availability');$('#availability-list').innerHTML=list.length?list.map(r=>`<div class="availability-row"><span>${days[r.weekday]} · ${r.start_time.slice(0,5)}–${r.end_time.slice(0,5)}</span><button class="text-button" data-remove-rule="${r.id}" aria-label="${days[r.weekday]} ${r.start_time.slice(0,5)} aralığını sil">Sil ×</button></div>`).join(''):'<p class="small">Henüz çalışma saati eklenmedi.</p>';}
async function loadAppointments(){
  try {const list=await api('/api/appointments'); const therapist=state.user?.role==='therapist';
    $('#appointments-list').innerHTML=list.length?list.map(a=>{const future=new Date(a.starts_at)>new Date();return `<article class="appointment"><div><span class="badge ${a.status}">${statuses[a.status]}</span><h3 style="margin-top:10px">${esc(therapist?a.client_name:a.therapist_name)}</h3><p>${dateLabel(a.starts_at)} – ${timeLabel(a.ends_at)} · Türkiye saati</p><p>${a.session_price!==null?money(a.session_price):'Ücret kaydı bulunmuyor'}</p>${therapist&&(a.mood||a.expectations.length)?`<p>Danışanın paylaştıkları: ${esc(moods[a.mood]||'')} ${esc(a.expectations.join(', '))}</p>`:''}</div><div class="appointment-actions">${therapist&&a.status==='pending'&&future?`<button class="secondary" data-appointment="${a.id}" data-status="confirmed">Onayla</button>`:''}${therapist&&a.status==='confirmed'&&new Date(a.ends_at)<=new Date()?`<button class="secondary" data-appointment="${a.id}" data-status="completed">Seans tamamlandı</button>`:''}${['pending','confirmed'].includes(a.status)&&future?`<button class="text-button" data-appointment="${a.id}" data-status="cancelled">İptal et</button>`:''}${!therapist&&a.status==='completed'&&!a.reviewed?`<button class="secondary" data-review="${a.therapist_id}">Değerlendir ☆</button>`:''}${!therapist&&a.reviewed?'<span class="small">Değerlendirmen paylaşıldı</span>':''}</div></article>`;}).join(''):'<div class="empty"><h3>Takviminde yeni bir sayfa.</h3><p>Randevuların oluştuğunda burada görünecek.</p></div>';
  }catch(e){$('#appointments-list').innerHTML=`<p class="error-state">${esc(e.message)}</p>`;}
}
document.addEventListener('click',async event=>{
  const b=event.target.closest('button');if(!b)return;
  if(b.dataset.close){$('#'+b.dataset.close).close();return;}
  if(b.dataset.mood){state.mood=b.dataset.mood;$$('[data-mood]').forEach(x=>x.setAttribute('aria-pressed',x===b));renderStep();}
  if(b.dataset.expectation){const x=b.dataset.expectation;state.expectations.has(x)?state.expectations.delete(x):state.expectations.add(x);b.setAttribute('aria-pressed',state.expectations.has(x));renderStep();}
  if(b.dataset.profile)await openProfile(b.dataset.profile);
  if(b.dataset.slot){state.selectedSlot=b.dataset.slot;$$('[data-slot]').forEach(x=>x.setAttribute('aria-pressed',x===b));$('#book-button').disabled=false;$('#booking-message').textContent='';}
  if(b.dataset.review){state.reviewTherapist=b.dataset.review;$('#review-form').reset();message($('#review-form'),'');$('#review-dialog').showModal();}
  if(b.dataset.removeRule){b.disabled=true;try{await api('/api/therapists/me/availability/'+b.dataset.removeRule,{method:'DELETE'});await loadAvailability();}catch(e){toast(e.message);b.disabled=false;}}
  if(b.dataset.appointment){if(b.dataset.status==='cancelled'&&!confirm('Bu randevuyu iptal etmek istiyor musun?'))return;b.disabled=true;try{await api('/api/appointments/'+b.dataset.appointment,{method:'PATCH',body:JSON.stringify({status:b.dataset.status})});await loadAppointments();toast('Randevu güncellendi.');}catch(e){toast(e.message);b.disabled=false;}}
  switch(b.dataset.action){case 'login':showAuth();break;case 'logout':logout();break;case 'home':showHome();window.scrollTo({top:0,behavior:'smooth'});break;case 'browse':await loadTherapists();break;case 'dashboard':case 'refresh-dashboard':await showDashboard();break;case 'register-therapist':showAuth('register');$('#auth-form').elements.role.value='therapist';break;}
});
$('#next-step').addEventListener('click',async()=>{if(state.step===1){state.step=2;renderStep();}else{const b=$('#next-step');b.disabled=true;await loadTherapists(true);b.disabled=false;}});
$('#back-step').addEventListener('click',()=>{state.step=1;renderStep();});
$('#auth-toggle').addEventListener('click',()=>{state.authMode=state.authMode==='login'?'register':'login';updateAuth();});
$('#auth-form').addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget;setBusy(f,true);message(f,'');const data=Object.fromEntries(new FormData(f));try{if(state.authMode==='register')await api('/register',{method:'POST',body:JSON.stringify(data)});const token=await api('/login',{method:'POST',body:JSON.stringify({email:data.email,password:data.password})});state.token=token.access_token;sessionStorage.setItem('iyi-token',state.token);state.user=await api('/me');renderAccount();$('#auth-dialog').close();f.reset();toast('Hoş geldin, '+state.user.full_name.split(' ')[0]+'.');await showDashboard();}catch(err){message(f,err.message);}finally{setBusy(f,false);}});
$('#profile-form').addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget;setBusy(f,true);message(f,'');const data=Object.fromEntries(new FormData(f));data.education=data.education.split('\n').map(x=>x.trim()).filter(Boolean);data.specialties=[...f.querySelectorAll('[name=specialty]:checked')].map(x=>x.value);delete data.specialty;data.session_minutes=Number(data.session_minutes);try{const p=await api('/api/therapists/me',{method:'PUT',body:JSON.stringify(data)});message(f,'Profilin kaydedildi.',true);$('#verification-state').textContent=p.is_verified?'✓ Profilin doğrulanmış ve yayında.':'Profilin doğrulama bekliyor.';await loadAvailability();}catch(err){message(f,err.message);}finally{setBusy(f,false);}});
$('#availability-form').addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget;setBusy(f,true);message(f,'');const data=Object.fromEntries(new FormData(f));data.weekday=Number(data.weekday);try{await api('/api/therapists/me/availability',{method:'POST',body:JSON.stringify(data)});await loadAvailability();message(f,'Çalışma aralığı eklendi.',true);}catch(err){message(f,err.message);}finally{setBusy(f,false);}});
$('#review-form').addEventListener('submit',async e=>{e.preventDefault();const f=e.currentTarget;setBusy(f,true);message(f,'');const data=Object.fromEntries(new FormData(f));data.rating=Number(data.rating);data.therapist_id=state.reviewTherapist;try{await api('/api/reviews',{method:'POST',body:JSON.stringify(data)});$('#review-dialog').close();toast('Değerlendirmen yayınlandı.');await loadAppointments();}catch(err){message(f,err.message);}finally{setBusy(f,false);}});
async function init(){renderAccount();try{const options=await api('/api/options');state.specialties=options.specialties;$('#expectation-options').innerHTML=state.specialties.map(x=>`<button class="choice" data-expectation="${esc(x)}" aria-pressed="false">${esc(x)} <span aria-hidden="true">＋</span></button>`).join('');checkboxOptions();}catch(e){toast(e.message);}if(state.token){try{state.user=await api('/me');renderAccount();}catch{logout(false);}}}
init();
