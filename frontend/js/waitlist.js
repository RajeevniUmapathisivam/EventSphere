const Waitlist = (() => {
    function countdown(entry) {
        return `<p class="waitlist-countdown" data-countdown="${entry.ticket_category_id}">
            <span data-time-left>Seat held for <span role="timer" aria-live="off">--:--</span></span>
            <span data-hold-ended hidden>Hold ended. Checking availability…</span>
        </p>`;
    }

    function monitor(container, render, eventId) {
        let snapshot;
        let deadlines = new Map();
        let request;
        let poll;
        let tick;
        const checkedExpiry = new Set();
        const quietlyRefresh = () => refresh().catch(() => {});

        function updateCountdowns() {
            let hasTimeLeft = false;
            for (const label of container.querySelectorAll("[data-countdown]")) {
                const category = Number(label.dataset.countdown);
                const offer = deadlines.get(category);
                if (!offer) continue;
                const seconds = Math.max(0, Math.ceil((offer.deadline - performance.now()) / 1000));
                const timer = label.querySelector('[role="timer"]');
                const action = label.parentElement.querySelector("[data-wait-action]");
                const ended = seconds === 0;
                label.querySelector("[data-time-left]").hidden = ended;
                label.querySelector("[data-hold-ended]").hidden = !ended;
                if (action) action.hidden = ended;
                if (seconds === 0) {
                    if (!checkedExpiry.has(offer.key)) {
                        checkedExpiry.add(offer.key);
                        if (!request) quietlyRefresh();
                    }
                    continue;
                }
                hasTimeLeft = true;
                const minutes = String(Math.floor(seconds / 60)).padStart(2, "0");
                const remainder = String(seconds % 60).padStart(2, "0");
                const labelTime = minutes + ":" + remainder;
                if (timer.textContent !== labelTime) timer.textContent = labelTime;
            }
            clearTimeout(tick);
            if (hasTimeLeft && !document.hidden) tick = setTimeout(updateCountdowns, 250);
        }

        async function sync(force) {
            const entries = (await ES.api("/waitlist")).filter(entry => eventId === undefined || entry.event_id === eventId);
            const next = JSON.stringify(entries.map(entry => [entry.ticket_category_id, entry.status, entry.expires_at]));
            const sampledAt = performance.now();
            deadlines = new Map(entries.filter(entry => entry.status === "offered" && entry.remaining_ms !== null)
                .map(entry => [entry.ticket_category_id, {
                    key: entry.ticket_category_id + ":" + entry.expires_at,
                    deadline: sampledAt + entry.remaining_ms,
                }]));
            if (next !== snapshot || force) {
                await render(entries);
                snapshot = next;
            }
            return entries.some(entry => entry.status === "waiting" || entry.status === "offered");
        }

        async function refresh(force = false) {
            if (request) {
                if (!force) return request;
                await request.catch(() => {});
                return refresh(true);
            }
            clearTimeout(poll);
            let active = true;
            request = sync(force);
            try {
                active = await request;
                updateCountdowns();
            } finally {
                request = null;
                if (active && !document.hidden) poll = setTimeout(quietlyRefresh, 5000);
            }
        }

        document.addEventListener("visibilitychange", () => {
            clearTimeout(poll);
            clearTimeout(tick);
            if (!document.hidden && snapshot !== undefined) {
                updateCountdowns();
                quietlyRefresh();
            }
        });
        return {refresh};
    }

    return {countdown, monitor};
})();
