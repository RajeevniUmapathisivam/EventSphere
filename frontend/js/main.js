ES.run(async () => {
    const events = await ES.api("/events");
    const keyword = ES.get("keyword");
    const category = ES.get("category");
    const categories = [...new Set(events.map(event => event.category))].sort();
    for (const name of categories) category.add(new Option(name, name));
    const month = new Intl.DateTimeFormat(undefined, {month: "short"});
    const time = new Intl.DateTimeFormat(undefined, {weekday: "short", hour: "numeric", minute: "2-digit"});

    function render() {
        const search = keyword.value.trim().toLowerCase();
        const results = events.filter(event =>
            (!category.value || category.value === event.category) &&
            [event.title, event.venue, event.description].some(text => text.toLowerCase().includes(search))
        );
        ES.get("events").innerHTML = results.map(event => {
            const start = new Date(event.start_time);
            return `<article class="card event-card">
                <div class="event-heading">
                    <time class="date-card" datetime="${ES.escape(event.start_time)}">
                        <strong>${start.getDate()}</strong><span>${ES.escape(month.format(start))}</span>
                    </time>
                    <span class="pill">${ES.escape(event.category)}</span>
                </div>
                <div>
                    ${ES.image(event)}
                    <h3>${ES.escape(event.title)}</h3>
                    <div class="event-meta">
                        <p>${ES.escape(time.format(start))}</p>
                        <p>${ES.escape(event.venue)} · ${ES.escape(event.location)}</p>
                    </div>
                    <p class="event-description">${ES.escape(event.description)}</p>
                </div>
                <a class="button" href="/event-details.html?id=${event.id}"
                    aria-label="View tickets for ${ES.escape(event.title)}">View tickets</a>
            </article>`;
        }).join("") || '<p class="muted">No matching events.</p>';
    }
    keyword.addEventListener("input", render);
    category.addEventListener("change", render);
    render();
});
