/* Carethropic — voice helpers. Browser speech only: nothing here reaches the model.
   speak() reads text in the record's language; listen() turns one utterance into text.
   The on/off preference is per browser (localStorage) so an elder's tablet remembers it. */
window.CarethropicVoice = (() => {
  const KEY = 'carethropic.voice';
  const synth = window.speechSynthesis;
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  let enabled = (() => { try { return localStorage.getItem(KEY) === 'on'; } catch (e) { return false; } })();
  let voices = [];
  const refresh = () => { try { voices = synth ? synth.getVoices() : []; } catch (e) { voices = []; } };
  if (synth) { refresh(); synth.onvoiceschanged = refresh; }

  function pick(bcp47) {
    const lang = bcp47.toLowerCase(); const base = lang.split('-')[0];
    return voices.find((v) => v.lang.toLowerCase() === lang) || voices.find((v) => v.lang.toLowerCase().startsWith(base)) || null;
  }
  function speak(text, bcp47, { force = false, rate = 0.92 } = {}) {
    if (!synth || !text || (!enabled && !force)) return false;
    try {
      synth.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.lang = bcp47 || 'en-US'; u.rate = rate; const v = pick(u.lang); if (v) u.voice = v;
      synth.speak(u);
      return true;
    } catch (e) { return false; }
  }
  function stop() { try { synth && synth.cancel(); } catch (e) { } }
  function listen(bcp47, onResult, onError) {
    if (!SR) { onError && onError('unsupported'); return null; }
    const rec = new SR(); rec.lang = bcp47 || 'en-US'; rec.interimResults = false; rec.maxAlternatives = 1;
    rec.onresult = (ev) => onResult(ev.results[0][0].transcript);
    rec.onerror = (ev) => onError && onError(ev.error || 'error');
    stop(); rec.start();
    return rec;
  }
  function setEnabled(on) { enabled = !!on; try { localStorage.setItem(KEY, enabled ? 'on' : 'off'); } catch (e) { } if (!enabled) stop(); }
  return { speak, stop, listen, setEnabled, get enabled() { return enabled; }, get canSpeak() { return !!synth; }, get canListen() { return !!SR; } };
})();
