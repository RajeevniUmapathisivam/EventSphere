const authForm = ES.get("auth-form");
ES.submit(authForm, async () => {
    const data = Object.fromEntries(new FormData(authForm));
    const action = authForm.dataset.action;
    const result = await ES.api("/auth/" + action, "POST", data);
    if (action === "login") {
        location.href = ES.dashboards[result.user.role][0];
    } else {
        authForm.reset();
        ES.notice(result.message);
    }
});
