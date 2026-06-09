/**
 * WebSocket Interceptor — paste into browser console on the MM Fantasy page.
 * It patches WebSocket so we can read every message the page sends/receives.
 * Run this BEFORE navigating to the player list, or refresh after pasting.
 *
 * After running: browse to the player selection view and watch the console —
 * look for messages containing "player" or a long array of objects.
 * Copy the relevant raw message text and share it.
 */

(function () {
  const OrigWS = window.WebSocket;

  window.WebSocket = function (url, protocols) {
    const ws = protocols ? new OrigWS(url, protocols) : new OrigWS(url);
    console.log('%c[WS OPEN]', 'color:green;font-weight:bold', url);

    const origSend = ws.send.bind(ws);
    ws.send = function (data) {
      console.log('%c[WS SEND]', 'color:blue', typeof data === 'string' ? data.slice(0, 500) : '[binary]');
      return origSend(data);
    };

    ws.addEventListener('message', (e) => {
      const msg = e.data;
      if (typeof msg !== 'string') return;

      // Highlight messages that look like player data
      const lower = msg.toLowerCase();
      const interesting = lower.includes('player') || lower.includes('squad') || lower.includes('transfer') || lower.includes('price') || lower.includes('forward') || lower.includes('midfielder');

      if (interesting) {
        console.log('%c[WS RECV ★ PLAYER DATA]', 'color:red;font-weight:bold;font-size:14px', msg.slice(0, 2000));
      } else if (msg.length > 50) {
        console.log('%c[WS RECV]', 'color:gray', msg.slice(0, 300));
      }
    });

    ws.addEventListener('close', (e) => {
      console.log('%c[WS CLOSE]', 'color:orange', url, e.code, e.reason);
    });

    return ws;
  };

  // Copy prototype so instanceof checks keep working
  window.WebSocket.prototype = OrigWS.prototype;
  Object.keys(OrigWS).forEach(k => { window.WebSocket[k] = OrigWS[k]; });

  console.log('%c[WS interceptor active — now navigate to the player selection page]', 'color:purple;font-weight:bold;font-size:14px');
})();
