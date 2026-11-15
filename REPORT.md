# IT4123 ICA 02 — EventSphere

**Live HTTPS URL** — Add the deployed address here.  
**GitHub repository** — Add the repository address here.

## Implementation and requirements

| Assignment area | Implementation |
| --- | --- |
| A1 Accounts and roles | Attendee registration, sign-in, hashed passwords and separate admin, staff and attendee authorization on pages and APIs. |
| A2 Venue management | Admin can create and edit the venue name, location, capacity, description, image URL, hourly price and private-hire status. |
| A3 Event management | Event category, venue, start and end, description, multiple ticket categories, drafts, publication and cancellation. Venue and turnaround constraints apply when publishing. |
| A4 Browsing and booking | Mobile layout, keyword and category filters, live allocation at booking, simulated payment reference, booking history and policy-based refunds. |
| A5 QR and gate admission | Individual random QR codes, browser camera scanner and manual entry. The selected event, ticket status and check-in window determine admission. |
| A6 Private hire | Whole-venue time slot, guest count, purpose, price and immediate confirmation or escalation. Conflicts return a usable alternative when a suitable venue exists. Admin can approve or reject escalated requests. |
| A7 Admin dashboard | Sales, net simulated revenue, check-ins, allocated ticket count, venue capacity and conversation logs. |
| B Agent design | Five rule-driven agents, persistent state, JSON messaging, refusal and proposal reasons, broadcast notifications, and a scheduled waitlist sweep. |
| C Optional features | Time-limited waitlist holds with a visible countdown on the attendee dashboard and event page, background expiry, and automatic re-offer to the next attendee. |

## Architecture and decision rules

The browser uses the same FastAPI origin for pages and API calls. Pydantic validates inputs. Public registration assigns only the attendee role. The server uses PBKDF2-HMAC-SHA256 password hashes with individual salts. Session IDs are random and stored as hashes. Write requests must present the CSRF token from their browser session.

The message bus serializes envelopes as JSON and records the sender, receiver, performative, content, timestamp and conversation ID. It accepts REQUEST, AGREE, REFUSE, PROPOSE, INFORM and FAILURE. When a handler needs another agent, it schedules a message through the bus, which delivers it within the same transaction. Broadcast INFORM messages go to the NotificationAgent subscriber. The dashboard hides ticket tokens from the message display.

| Agent and goal | Persistent state | Decision rules |
| --- | --- | --- |
| VenueAgent avoids calendar clashes | Venues, ticket allocations, published events and confirmed hire slots | Requires a future event start, valid calendar range and allocation within venue capacity. Published events and confirmed hires need 30 minutes between activities. Drafts hold no calendar slot. Venue edits cannot lower capacity below an existing future event allocation or confirmed guest count. Hire must be in the future, at a venue open for hire, and within capacity. Price is hourly rate times the number of hours. A feasible request above 50 guests or six hours is escalated. Other feasible requests are confirmed. Conflicts or unsuitable venues trigger proposals for suitable venues at the same time or the next free slot. An approval rechecks the calendar, hire status and capacity. |
| BookingAgent allocates seats and refunds payments | Ticket counts, booking history and simulated payments | Sells 1–6 tickets per booking, only before a published event starts, and only from the selected category. Active holds are excluded from public stock. An attendee can claim their unexpired hold during booking. A successful booking records a unique simulated payment. Before the event starts, an attendee receives 100% at least 24 hours before the start and 50% inside that period, rounded half-up to cents. An attendee cannot cancel once the event has started or any ticket was used. Admin cancellation refunds all active paid bookings in full and releases their tickets. |
| TicketAgent issues and admits individual tickets | Random ticket codes, ticket states and admission records | Issues one random 256-bit token per paid ticket. Issues at most one set per booking. Rejects unknown code, wrong event, cancelled status, used status, or requests outside the window from one hour before the start until the end. A successful scan marks the ticket used and records one admission. Cancelled bookings invalidate their tickets. |
| WaitlistAgent allocates released seats in order | Queue order, status and hold expiry | Accepts one active entry per attendee and category, only when the category has no publicly available seats for a future published event. Offers one seat per waiting attendee, oldest entry first. Holds last up to 15 minutes and stop at event start. A successful purchase claims the hold. A scheduled five-second sweep expires holds and re-offers seats with no browser action. Event cancellation closes the queue. |
| NotificationAgent informs the affected user | Per-attendee in-app notifications | Receives broadcast INFORM messages for hire decisions, completed bookings, refunds, check-ins, waitlist offers, expiry and closure. Each message supplies the affected user ID. The agent writes the matching notification, visible only to that user. |

## Concurrency and testing

The bus takes a database write lock before reading any state used for a decision. SQLite obtains its writer lock and PostgreSQL locks a single decision row. The checks and the resulting booking, payment, ticket, waitlist and log updates commit together. A second simultaneous request sees the first committed decision and cannot claim the same seat or admit the same ticket. The same transaction protects venue calendar decisions. A failed conversation rolls back and records a FAILURE when the database is available.

Run Pytest from `backend` as described in the README. The tests cover accounts, role boundaries, CSRF, venue editing and capacity, drafts and overlapping activities, concurrent sale of the last seat, payment and QR issuance, double check-in, wrong-event and time-window rejection, cancelled tickets, refunds, hire proposals and approvals, scheduled waitlist re-offers, notifications, conversation traces and restart persistence.

The countdown uses the remaining time reported by the server and the browser's elapsed-time clock. When the countdown ends, the browser hides the held-seat action and refreshes the waitlist. The WaitlistAgent owns the expiry timestamp and re-offers the seat without a user action. Waiting attendees' pages refresh while open so a new offer appears without a manual reload.

A 375 px Chrome walkthrough used a shortened hold on a temporary test server. It verified a decreasing countdown, expiry on both attendee screens, automatic re-offer to a second attendee, and that attendee claiming the seat. The app uses the 15-minute maximum in normal operation.

All 19 tests passed on SQLite and PostgreSQL. The Windows launcher installed and started the application from a clean ZIP extraction. The redesigned app was also tested from an extracted ZIP in Chrome at 375 px and desktop width, over local HTTPS with PostgreSQL and hosted-demo settings. That walkthrough verified the campus sample, filters, simulated booking, QR ticket display, wrong-event rejection, QR decoding using a simulated camera stream, duplicate rejection, and admin metrics. The Render Blueprint passed validation against Render's published schema.

## Demo accounts for the viva

| Role | Email | Password to put in the LMS copy |
| --- | --- | --- |
| Admin | admin@example.com | Insert the hosted admin password |
| Staff | staff@example.com | Insert the hosted staff password |
| Attendee | attendee@example.com | Insert the hosted attendee password |

Include the actual live URL, GitHub URL, and the three hosted demo credentials in the PDF submitted to the LMS. Add the lecturer as a collaborator if the repository is private.
