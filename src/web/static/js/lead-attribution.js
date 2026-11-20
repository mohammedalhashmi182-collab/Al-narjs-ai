window.narjisLeadAttribution = function (data) {
    data.attribution_consent = data.attribution_consent === 'yes';
    if (!data.attribution_consent) return;

    const query = new URLSearchParams(window.location.search);
    for (const key of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term', 'fbclid']) {
        if (query.has(key)) data[key] = query.get(key);
    }
};
