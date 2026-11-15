const eventId = Number(new URLSearchParams(location.search).get("id"));
const list = ES.get("categories");
const waitlistMonitor = Waitlist.monitor(list, loadEvent, eventId);

async function loadEvent(waitlist) {
    if (!Number.isSafeInteger(eventId) || eventId < 1) throw new Error("Select an event from the events page.");
    let event;
    try {
        event = await ES.api("/events/" + eventId);
    } catch (error) {
        if (error.status !== 404) throw error;
        list.replaceChildren();
        ES.notice("This event is no longer available.", true);
        return;
    }
    const {user} = await ES.session;
    const attendee = user?.role === "attendee";
    ES.get("title").textContent = event.title;
    const label = ES.get("event-category");
    label.textContent = event.category;
    label.hidden = false;
    ES.get("summary").innerHTML = `
        ${ES.image(event)}
        <p><strong>${ES.escape(event.venue)}</strong> · ${ES.escape(event.location)}</p>
        <p>${ES.date(event.start_time)} to ${ES.date(event.end_time)}</p>
        <p>${ES.escape(event.description)}</p>`;
    list.innerHTML = event.ticket_categories.map(item => {
        const entry = waitlist.find(row => row.ticket_category_id === item.id);
        const isOffered = entry?.status === "offered";
        const hasOffer = isOffered && entry.remaining_ms > 0;
        const canBook = item.available > 0 || hasOffer;
        let action = "";
        if (event.booking_open && attendee && canBook) {
            action = `<form data-category="${item.id}" ${hasOffer ? "data-wait-action" : ""}>
                <label>Quantity <input name="quantity" type="number" min="1"
                    max="${Math.min(6, item.available + Number(hasOffer))}" value="1" required></label>
                <button>Book and simulate payment</button>
            </form>`;
        } else if (event.booking_open && attendee) {
            action = entry && ["waiting", "offered"].includes(entry.status)
                ? "<p>You are on the waitlist.</p>"
                : `<button class="secondary" data-wait="${item.id}">Join waitlist</button>`;
        } else if (!user && event.booking_open) {
            action = '<a class="button secondary" href="/login.html">Sign in to book</a>';
        } else if (!event.booking_open) {
            action = "<p>Booking has closed.</p>";
        }
        return `<article class="card ticket-category"><h3>${ES.escape(item.name)}</h3>
            <p><span class="ticket-price">${ES.money(item.price)}</span> <span class="muted">per ticket</span></p>
            <p class="pill">${item.available ? item.available + " available" : "Sold out"}</p>
            ${event.booking_open && entry?.status === "expired" ? '<p class="helper">Your hold expired.</p>' : ""}
            ${event.booking_open && isOffered ? Waitlist.countdown(entry) : ""}${action}</article>`;
    }).join("");
}

list.addEventListener("submit", event => {
    event.preventDefault();
    const form = event.target;
    if (!confirm("Confirm this booking and simulate payment?")) return;
    ES.run(async () => {
        const payment = await ES.api("/bookings", "POST", {
            event_id: eventId, ticket_category_id: Number(form.dataset.category),
            quantity: Number(form.elements.quantity.value),
        });
        ES.notice("Booked. Payment reference " + payment.payment_reference + ". Your QR tickets are under My bookings.");
        await waitlistMonitor.refresh(true);
    }, event.submitter);
});

ES.click(list, "wait", async button => {
    await ES.api("/waitlist", "POST", {event_id: eventId, ticket_category_id: Number(button.dataset.wait)});
    ES.notice("You joined the waitlist.");
    await waitlistMonitor.refresh(true);
});

ES.run(async () => {
    const {user} = await ES.session;
    if (user?.role === "attendee") await waitlistMonitor.refresh();
    else await loadEvent([]);
});
