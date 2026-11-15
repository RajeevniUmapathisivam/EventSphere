const hireForm = ES.get("hire-form");
const alternatives = ES.get("alternatives");
let suggestions = [];
const waitlistCards = ES.get("waitlist");
const waitlistMonitor = Waitlist.monitor(waitlistCards, entries => {
    waitlistCards.innerHTML = entries.map(item => `<article class="card">
        <h3>${ES.escape(item.event)}</h3><p>${ES.escape(item.category)} · ${ES.escape(item.status)}</p>
        ${item.status === "offered" ? `${Waitlist.countdown(item)}
            <a class="button" data-wait-action href="/event-details.html?id=${item.event_id}">Book held seat</a>` : ""}
    </article>`).join("") || "<p>No waitlist entries.</p>";
});

async function load() {
    const [bookings, tickets, venues, hires, notices] = await Promise.all([
        ES.api("/bookings"), ES.api("/tickets"), ES.api("/venues"),
        ES.api("/hires"), ES.api("/notifications"),
    ]);
    const select = hireForm.elements.venue_id;
    const current = select.value;
    select.replaceChildren(...venues.map(venue => new Option(
        `${venue.name} · ${venue.capacity} guests · ${ES.money(venue.hourly_rate)}/hour`, venue.id,
    )));
    if (venues.some(venue => String(venue.id) === current)) select.value = current;
    ES.get("hire-submit").disabled = !venues.length;
    if (!venues.length) ES.notice("No venues are open for hire.", false, "hire-response");
    ES.get("bookings").innerHTML = bookings.map(item => `<article class="card">
        <h3>${ES.escape(item.event)}</h3>
        <p>${ES.escape(item.category)} · ${item.quantity} ticket(s) · <strong>${ES.escape(item.status)}</strong></p>
        <p>Paid ${ES.money(item.paid)} · Refund ${ES.money(item.refund)}</p>
        <p>Booking ${ES.escape(item.reference)}<br>Payment ${ES.escape(item.payment_reference)}</p>
        ${item.can_cancel ? `<button class="danger" data-cancel="${item.id}">Cancel booking</button>` : ""}
    </article>`).join("") || "<p>You have no bookings yet.</p>";
    const currentTime = Date.now();
    const canUse = ticket => ticket.status === "valid" && Date.parse(ticket.end_time) > currentTime;
    tickets.sort((first, second) => {
        const firstActive = canUse(first);
        const secondActive = canUse(second);
        if (firstActive !== secondActive) return Number(secondActive) - Number(firstActive);
        const startDifference = Date.parse(first.start_time) - Date.parse(second.start_time);
        return firstActive ? startDifference : -startDifference;
    });
    ES.get("tickets").innerHTML = tickets.map(item => `<article class="card qr-ticket">
        <p class="status" data-state="${ES.escape(item.status)}">${ES.escape(item.status)}</p>
        <h3>${ES.escape(item.event)}</h3>
        <p class="muted">${ES.escape(item.category)} · ${ES.date(item.start_time)}</p>
        ${item.qr_image ? `<img class="qr" src="${item.qr_image}" alt="Ticket QR code" width="240" height="240">
        <p class="ticket-code helper">Manual ticket code <code>${ES.escape(item.qr_code)}</code></p>` : ""}
    </article>`).join("") || "<p>Your tickets will appear here after simulated payment.</p>";
    ES.get("hires").innerHTML = hires.map(item => `<article class="card">
        <h3>${ES.escape(item.venue)}</h3><p>${ES.date(item.start_time)} to ${ES.date(item.end_time)}</p>
        <p>${ES.escape(item.purpose)} · ${item.guests} guests</p>
        <p class="status">${ES.escape(item.status)} · ${ES.money(item.price)}</p>
    </article>`).join("") || "<p>No hire requests yet.</p>";
    ES.get("notifications").innerHTML = notices.map(item => `<article class="card">
        <h3>${ES.escape(item.title)}</h3><p>${ES.escape(item.message)}</p>
    </article>`).join("") || "<p>No notifications yet.</p>";
}

ES.click(ES.get("bookings"), "cancel", async button => {
    if (!confirm("Cancel this booking under the stated refund policy?")) return;
    const result = await ES.api(`/bookings/${button.dataset.cancel}/cancel`, "POST");
    ES.notice("Booking cancelled. Simulated refund " + ES.money(result.refund) + ".");
    await Promise.all([load(), waitlistMonitor.refresh()]);
});

ES.submit(hireForm, async fields => {
    alternatives.replaceChildren();
    const result = await ES.api("/hires", "POST", {
        venue_id: Number(fields.venue_id.value),
        requested_date: new Date(fields.requested_date.value).toISOString(),
        duration_hours: Number(fields.duration_hours.value),
        expected_attendees: Number(fields.expected_attendees.value),
        purpose: fields.purpose.value,
    });
    if (result.decision === "PROPOSE") {
        suggestions = result.alternatives;
        ES.notice(result.reason + " Choose an alternative below.", false, "hire-response");
        alternatives.innerHTML = suggestions.map((option, index) => `<article class="card">
            <h3>${ES.escape(option.venue_name)}</h3>
            <p>${ES.date(option.start_time)} to ${ES.date(option.end_time)}</p><p>${ES.money(option.price)}</p>
            <button type="button" class="secondary" data-alternative="${index}">Use this alternative</button>
        </article>`).join("");
        return;
    }
    const summary = result.status === "confirmed" ? "Hire confirmed." : "Hire sent to the admin for review.";
    ES.notice(summary + " Quoted price " + ES.money(result.price) + ".", false, "hire-response");
    hireForm.reset();
    await load();
}, "hire-response");

ES.click(alternatives, "alternative", button => {
    const choice = suggestions[Number(button.dataset.alternative)];
    hireForm.elements.venue_id.value = choice.venue_id;
    hireForm.elements.requested_date.value = ES.localInputDate(choice.start_time);
    ES.notice("Alternative selected. Submit the request to confirm availability.", false, "hire-response");
    alternatives.replaceChildren();
    ES.get("hire-submit").focus();
});

ES.run(load);
ES.run(() => waitlistMonitor.refresh());
