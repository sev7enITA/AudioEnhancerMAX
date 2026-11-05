/* First-party aggregate click routing. No storage, cookies or automatic events. */
(() => {
  'use strict';
  const sources = new Set(['website','linkedin','x','facebook','instagram','reddit','sourceforge','gearspace','kvr','product-hunt','youtube','bilibili','appinn','newsletter','unknown']);
  const campaigns = new Set(['launch-2026-11','field-test-2026-11']);
  const query = new URLSearchParams(location.search);
  const source = sources.has(query.get('utm_source')) ? query.get('utm_source') : 'website';
  const campaign = campaigns.has(query.get('utm_campaign')) ? query.get('utm_campaign') : 'launch-2026-11';
  document.querySelectorAll('a[data-aem-target]').forEach(link => {
    const params = new URLSearchParams({to:link.dataset.aemTarget,source,campaign,placement:link.dataset.aemPlacement || 'other'});
    link.href = `go.php?${params}`;
  });
  // Carry only allowlisted campaign names between project pages, in the URL.
  if (!query.has('utm_source')) return;
  document.querySelectorAll('a[href]').forEach(link => {
    if (link.hasAttribute('data-aem-target')) return;
    const url = new URL(link.href, location.href);
    if (url.origin === location.origin && url.pathname.startsWith('/AudioEnhancerMAX/') && /(?:\.html|\/)$/i.test(url.pathname)) {
      url.searchParams.set('utm_source', source);
      url.searchParams.set('utm_campaign', campaign);
      link.href = url.href;
    }
  });
})();
