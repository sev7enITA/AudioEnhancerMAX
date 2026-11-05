(() => {
  'use strict';
  const value = id => document.getElementById(id).value.trim();
  const report = document.getElementById('report');
  document.getElementById('feedback-form').addEventListener('submit', event => {
    event.preventDefault();
    report.value = `AudioEnhancerMAX field note\n\nEdition: ${value('edition')}\nEnvironment: ${value('environment') || 'Not supplied'}\nOutcome: ${value('outcome')}\n\nSteps and result\n${value('steps') || 'Not supplied'}\n\nListening observation\n${value('listening') || 'Not supplied'}\n\nReview controls and evidence\n${value('review') || 'Not supplied'}\n\nThese are observations from one test, not a general quality claim.\n`;
    document.getElementById('report-section').hidden = false;
    document.getElementById('feedback-status').textContent = 'Report created in this tab. Nothing has been submitted.';
  });
  document.getElementById('save-report').addEventListener('click', () => {
    const url = URL.createObjectURL(new Blob([report.value], {type:'text/plain;charset=utf-8'}));
    const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'AudioEnhancerMAX-field-note.txt'; anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  document.getElementById('github-report').addEventListener('click', () => {
    const url = new URL('https://github.com/sev7enITA/AudioEnhancerMAX/issues/new');
    url.searchParams.set('title', '[Field note] ' + value('edition'));
    url.searchParams.set('body', report.value);
    location.assign(url.href);
  });
})();
