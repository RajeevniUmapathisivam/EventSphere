const form = ES.get("checkin-form");
const video = ES.get("camera");
const start = ES.get("start-camera");
const stop = ES.get("stop-camera");
const canvas = document.createElement("canvas");
const context = canvas.getContext("2d", {willReadFrequently: true});
let stream;
let frame;

function stopCamera() {
    clearTimeout(frame);
    stream?.getTracks().forEach(track => track.stop());
    stream = null;
    video.srcObject = null;
    video.hidden = stop.hidden = true;
    start.hidden = false;
}

function scan() {
    if (!stream) return;
    if (video.readyState >= 2 && video.videoWidth) {
        const scale = Math.min(1, 640 / Math.max(video.videoWidth, video.videoHeight));
        canvas.width = Math.round(video.videoWidth * scale);
        canvas.height = Math.round(video.videoHeight * scale);
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height);
        const code = jsQR(pixels.data, pixels.width, pixels.height);
        if (code?.data) {
            form.elements.qr_code.value = code.data;
            stopCamera();
            form.requestSubmit(ES.get("checkin-submit"));
            return;
        }
    }
    frame = setTimeout(scan, 150);
}

start.onclick = () => ES.run(async () => {
    if (!form.elements.event_id.reportValidity()) return;
    if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Camera access requires HTTPS or localhost. Enter the ticket code manually.");
    }
    try {
        stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: {ideal: "environment"}}, audio: false});
        video.srcObject = stream;
        video.hidden = stop.hidden = false;
        start.hidden = true;
        await video.play();
        scan();
    } catch (error) {
        stopCamera();
        throw new Error("Camera unavailable. Check browser permissions or enter the ticket code manually.");
    }
}, start);
stop.onclick = stopCamera;
window.addEventListener("pagehide", stopCamera);
ES.submit(form, async fields => {
    stopCamera();
    const output = ES.get("message");
    try {
        const result = await ES.api("/staff/checkin", "POST", {
            event_id: Number(fields.event_id.value), qr_code: fields.qr_code.value.trim(),
        });
        ES.notice(result.message);
        fields.qr_code.value = "";
    } catch (error) {
        ES.notice(error.message, true);
        if (error.message.includes("already been used")) output.classList.add("warning");
    }
});
ES.run(async () => {
    const events = await ES.api("/staff/events");
    form.elements.event_id.replaceChildren(new Option("Select an event", ""),
        ...events.map(event => new Option(event.title + " · " + ES.date(event.start_time), event.id)));
    if (!events.length) ES.notice("There are no published events available for check-in.");
});
