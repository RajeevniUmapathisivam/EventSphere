const ES = (() => {
    const get = id => document.getElementById(id);
    const escapes = {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"};
    const escape = value => String(value ?? "").replace(/[&<>"']/g, char => escapes[char]);
    const money = value => new Intl.NumberFormat("en-LK", {style: "currency", currency: "LKR"}).format(value);
    const dateTime = new Intl.DateTimeFormat(undefined, {dateStyle: "medium", timeStyle: "short"});
    const date = value => dateTime.format(new Date(value));
    const localInputDate = value => {
        const valueDate = new Date(value);
        return new Date(valueDate.getTime() - valueDate.getTimezoneOffset() * 60_000).toISOString().slice(0, 16);
    };
    const dashboards = {
        admin: ["/organiser-dashboard.html", "Admin dashboard"],
        staff: ["/staff-dashboard.html", "Gate check-in"],
        attendee: ["/attendee-dashboard.html", "My bookings"],
    };
    const session = fetch("/api/auth/session", {cache: "no-store"}).then(response => {
        if (!response.ok) throw new Error("Could not start a browser session. Reload and try again.");
        return response.json();
    });

    async function api(path, method = "GET", payload) {
        const state = await session;
        const headers = {"X-CSRF-Token": state.csrf_token};
        if (payload !== undefined) headers["Content-Type"] = "application/json";
        const response = await fetch("/api" + path, {
            method, headers, cache: "no-store",
            body: payload === undefined ? undefined : JSON.stringify(payload),
        });
        const result = await response.json().catch(() => ({}));
        if (!response.ok) {
            const detail = Array.isArray(result.detail) ? result.detail.map(entry => entry.msg).join(" ") : result.detail;
            const error = new Error(detail || "The request failed (HTTP " + response.status + ").");
            error.status = response.status;
            throw error;
        }
        return result;
    }

    function notice(text, error = false, id = "message") {
        const output = get(id);
        if (!output) return;
        output.hidden = !text;
        output.classList.add("notice");
        output.classList.remove("warning");
        output.classList.toggle("error", error);
        output.textContent = text;
    }

    async function run(task, button, output = "message") {
        if (button) button.disabled = true;
        try {
            await task();
        } catch (error) {
            notice(error.message, true, output);
        } finally {
            if (button) button.disabled = false;
        }
    }

    function submit(form, task, output) {
        form.addEventListener("submit", event => {
            event.preventDefault();
            run(() => task(form.elements), event.submitter, output);
        });
    }

    function click(container, attribute, task) {
        container.addEventListener("click", event => {
            const button = event.target.closest(`button[data-${attribute}]`);
            if (button) run(() => task(button), button);
        });
    }

    const image = event => event.image_url
        ? `<img class="event-image" src="${escape(event.image_url)}" alt="${escape(event.venue)}" loading="lazy">` : "";

    session.then(({user}) => {
        const nav = get("account-nav");
        if (!user) {
            nav.innerHTML = '<a href="/login.html">Sign in</a><a class="button" href="/register.html">Register</a>';
            return;
        }
        const [url, label] = dashboards[user.role];
        const current = location.pathname === url ? ' aria-current="page"' : "";
        nav.innerHTML = `<a href="${url}"${current}>${label}</a><button class="secondary" id="logout">Sign out</button>`;
        get("logout").addEventListener("click", () => run(async () => {
            await api("/auth/logout", "POST");
            location.href = "/";
        }, get("logout")));
    }).catch(error => notice(error.message, true));

    return {get, escape, money, date, localInputDate, dashboards, session, api, notice, run, submit, click, image};
})();
