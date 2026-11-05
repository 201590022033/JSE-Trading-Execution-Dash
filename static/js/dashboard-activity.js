(() => {
  // The clock is useful while the dashboard is visible and recently used.
  // Closing or hiding it ends this tab's lease; a lost connection expires it.
  const client = crypto.randomUUID().replaceAll('-', '');
  const endpoint = '/api/v1/dashboard/activity';
  let lastInteraction = Date.now();
  let lastSent = 0;
  function send(active) {
    lastSent = Date.now();
    fetch(endpoint, {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({client,active}), keepalive:true}).catch(()=>{});
  }
  function update() {
    const active = !document.hidden && Date.now() - lastInteraction < 5 * 60 * 1000;
    send(active);
  }
  for (const event of ['pointerdown','pointermove','keydown','touchstart','wheel']) {
    document.addEventListener(event, () => {
      lastInteraction=Date.now();
      if (!document.hidden && Date.now()-lastSent>15000) send(true);
    }, {passive:true});
  }
  document.addEventListener('visibilitychange', update);
  window.addEventListener('pagehide', () => send(false));
  update();
  setInterval(update,30000);
})();
