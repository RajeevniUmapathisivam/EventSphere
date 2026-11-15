# EventSphere

IT4123 ICA 02 venue booking and digital ticketing. EventSphere uses FastAPI, Pydantic, a relational database, and a mobile-friendly HTML, CSS and JavaScript interface with Bootstrap CSS utilities. SQLite handles local use. The hosted build uses PostgreSQL.

## Run on another Windows PC

1. Install Python 3.11 or later and select **Add Python to PATH** during installation. The first setup needs internet access to install Python packages.
2. Extract the entire ZIP to a writable folder. Double-click **START_EVENTSPHERE.bat**.
3. Open **http://127.0.0.1:8000** in your browser. Keep the launch window open and press **Ctrl+C** there to shut down.
4. Sign in with a demo account below. Use the attendee account to view the preloaded bookings and QR tickets.

The app creates its local database and demo accounts on first launch. A database with no venues receives two venues, two published events, one draft, two paid bookings and three QR tickets. The sample is based on the University of Vavuniya's Pampaimadu campus. Venue names, events, prices and accounts are fictional demo records. Local records persist in `backend/eventsphere.sqlite3`. To try the sample independently of an existing project, extract the ZIP into a new folder.

| Role | Demo name | Email | Local demo password |
| --- | --- | --- | --- |
| Admin | Arul Selvan | admin@example.com | `DemoAdmin123!` |
| Staff | Meena Tharmalingam | staff@example.com | `DemoStaff123!` |
| Attendee | Kavitha Sivarajah | attendee@example.com | `DemoAttendee123!` |

### Manual setup and tests

Run from the extracted folder in PowerShell.

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run the tests in another terminal from `backend` after installing the packages.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

On macOS or Linux, use `python3 -m venv .venv` and replace the Windows environment path with `.venv/bin/python`. The tests use temporary SQLite files by default. Set `EVENTSPHERE_TEST_POSTGRES_URL` to a PostgreSQL URL with the `postgresql+psycopg://` scheme to run them in temporary schemas. The database user needs permission to create schemas.

## Demonstrate the workflows

**Vavuniya Tamil Cultural Evening** starts 30 minutes after the sample is created, so staff can try check-in immediately. The attendee can find its ticket codes under **My bookings**. **Vavuniya Student Web Development Workshop** starts seven days later. The admin can publish the **Pampaimadu Student Innovation Forum** draft.

- **Admin** creates or edits a venue, saves a draft event with ticket categories, and publishes it. Use a start time about 30 minutes from now to try both buying and check-in in one session. The dashboard shows sales, revenue after refunds, admissions and capacity. Click a conversation ID to follow related agent messages.
- **Attendee** searches or filters events, opens event details, and books with simulated payment. Open **My bookings** for the payment reference, QR ticket, cancellation, waitlist, and private hire. Register extra attendee accounts to demonstrate a sold-out category and a waitlist offer after the buyer cancels.
- **Staff** selects the matching event, then scans or enters the ticket code. Check-in opens one hour before the event and closes at the event end. Browser camera access requires localhost or HTTPS and camera permission. For a phone on a different network device, use the deployed HTTPS address.
- **Venue hire** is confirmed and priced immediately when it fits the routine rules. A request above 50 guests or six hours goes to the admin for review. The attendee can select and resubmit a proposed alternative when a venue is unsuitable or its slot is busy.

### Part C waitlist countdown demonstration

1. Publish a future event with a one-ticket category and book that ticket as an attendee.
2. Register two more attendees and join that category's waitlist in order. Keep their **My bookings → Waitlist** views open in separate browser profiles.
3. Cancel the original booking. The first attendee's **Seat held for** countdown appears automatically on the dashboard and ticket page. Holds last up to 15 minutes and end by the event's start time.
4. Leave the first offer unclaimed. The first attendee's hold ends, and the next attendee gets their own countdown. Use **Book held seat** on the second account to claim the ticket before its hold ends.

The browser displays time remaining from the server. The WaitlistAgent expires and re-offers seats automatically even with the attendee pages closed.

## Environment variables

The local defaults work without an `.env` file. To override them, copy `backend/.env.example` to `backend/.env` or set these variables in your hosting account.

| Variable | Use |
| --- | --- |
| `APP_ENV` | `development` locally. `production` requires PostgreSQL and sends secure session and CSRF cookies. |
| `DATABASE_URL` | Local SQLite file by default. Use the host's PostgreSQL connection URL in production. |
| `DEMO_ENABLED` | `1` to provision the three demo accounts on an empty database. Defaults to `1` locally and `0` in production. |
| `DEMO_DATA_ENABLED` | Seeds campus records when demo accounts are enabled and there are no venues. Defaults to `1` locally and `0` in production. The Render configuration explicitly enables the sample for the assignment demo. |
| `DEMO_ADMIN_PASSWORD`, `DEMO_STAFF_PASSWORD`, `DEMO_ATTENDEE_PASSWORD` | Set three individual passwords in the hosting dashboard when using demo accounts in production. They are applied when accounts are first created. |

## Deploy for the assignment

1. Push the extracted project files to GitHub with `render.yaml` at the repository root. The included Git ignore file excludes local settings, databases and Python environments.
2. In Render, choose **New → Blueprint** and select the GitHub repository. The included configuration creates the Python 3.13 web service and PostgreSQL database, connects them over Render's internal network, and seeds the campus demo on the empty database.
3. After the deploy succeeds, open the web service's HTTPS URL. In its **Environment** tab, reveal the three generated `DEMO_*_PASSWORD` values. Sign in with the demo email addresses above and the matching generated passwords. The local demo passwords are for your own PC.
4. Verify all three roles and staff camera access from a phone using the deployed HTTPS URL. Create an event starting about 30 minutes before the check-in demonstration if the preloaded cultural evening has passed.
5. Add the live HTTPS and GitHub links and hosted demo credentials to [the report](REPORT.md) before exporting it to PDF for LMS submission.

The Blueprint selects Render's free plans for the classroom demo. The web service sleeps when idle, which also pauses the waitlist timer until it wakes. The free database expires after 30 days. Use paid plans if the service and database must stay available beyond those limits.

[Render Blueprints](https://render.com/docs/infrastructure-as-code) · [Render free plan limits](https://render.com/docs/free)
