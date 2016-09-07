$( document ).ready(() => {
  setInterval(() => {
    var cname = $('#champ').text();
    if (cname != '') {
      var msg = new SpeechSynthesisUtterance(cname);
      window.speechSynthesis.speak(msg);
    }
  }, 5000);
});