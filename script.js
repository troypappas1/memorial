const thanksCount = document.getElementById("thanksCount");
const heartButton = document.getElementById("heartButton");
const buttonNote = document.getElementById("buttonNote");
const heartsLayer = document.getElementById("heartsLayer");
const messageForm = document.getElementById("messageForm");
const messageName = document.getElementById("messageName");
const messageText = document.getElementById("messageText");
const messageSubmit = document.getElementById("messageSubmit");
const messageStatus = document.getElementById("messageStatus");
const messagesList = document.getElementById("messagesList");
const photosGrid = document.getElementById("photosGrid");
const photoStatus = document.getElementById("photoStatus");
const statusBanner = document.getElementById("statusBanner");
const statusText = document.getElementById("statusText");
const copyServerCommand = document.getElementById("copyServerCommand");
const candleButton = document.getElementById("candleButton");
const candleNote = document.getElementById("candleNote");
const rotatingQuote = document.getElementById("rotatingQuote");

const API_ENDPOINT = "/api/thanks";
const MESSAGES_ENDPOINT = "/api/messages";
const PHOTOS_ENDPOINT = "/api/photos";
const CLICKED_KEY = "george-pappas-thanked";
const CANDLE_KEY = "george-pappas-candle";
const START_COMMAND = "python server.py";
const ROTATING_QUOTES = [
  "Every photo, word, and thank you keeps his story close.",
  "Love like this does not disappear. It keeps showing up in the people it touched.",
  "A memorial becomes warmer each time someone stops to remember with kindness.",
  "The smallest message can become a lasting comfort for family and friends."
];

let memorialMode = "offline";

function setMemorialStatus(mode, detail) {
  memorialMode = mode;
  statusBanner.classList.remove("is-live", "is-offline");
  statusBanner.classList.add(mode === "live" ? "is-live" : "is-offline");
  statusText.textContent = detail;
}

function setOfflineGuidance() {
  const fileMode = window.location.protocol === "file:";
  const detail = fileMode
    ? "Open this memorial through the local server so the live comments and heart counter can work. Run python server.py, then visit http://127.0.0.1:8000."
    : "The memorial server is not responding yet. Run python server.py in this folder, then refresh the page for live comments and the shared heart counter.";
  setMemorialStatus("offline", detail);
}

async function copyStartCommandToClipboard() {
  try {
    await navigator.clipboard.writeText(START_COMMAND);
    copyServerCommand.textContent = "Copied";
    window.setTimeout(() => {
      copyServerCommand.textContent = "Copy Start Command";
    }, 1600);
  } catch (error) {
    copyServerCommand.textContent = "Use: python server.py";
  }
}

function startRotatingQuotes() {
  let quoteIndex = 0;
  window.setInterval(() => {
    quoteIndex = (quoteIndex + 1) % ROTATING_QUOTES.length;
    rotatingQuote.textContent = ROTATING_QUOTES[quoteIndex];
  }, 4200);
}

async function loadCount() {
  buttonNote.classList.add("is-loading");
  buttonNote.textContent = "Loading shared gratitude count...";

  try {
    const response = await fetch(API_ENDPOINT, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Unable to load count");
    }

    const data = await response.json();
    thanksCount.textContent = Number(data.count || 0).toLocaleString();
    setMemorialStatus("live", "Live memorial connected. Comments and the all-time heart counter are active.");

    if (localStorage.getItem(CLICKED_KEY) === "true") {
      buttonNote.textContent = "Your thanks has already been added. George is remembered.";
    } else {
      buttonNote.textContent = "Click the heart to leave a moment of thanks.";
    }
  } catch (error) {
    thanksCount.textContent = "0";
    buttonNote.textContent = "Start the memorial server to load the live all-time count.";
    setOfflineGuidance();
  } finally {
    buttonNote.classList.remove("is-loading");
  }
}

function formatMessageDate(value) {
  return new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function renderMessages(messages) {
  if (!messages.length) {
    messagesList.innerHTML = '<div class="empty-messages">No messages yet. Be the first to leave a remembrance.</div>';
    return;
  }

  messagesList.innerHTML = messages
    .map(
      (message) => `
        <article class="message-item">
          <div class="message-meta">
            <div class="message-author">${escapeHtml(message.name)}</div>
            <div class="message-date">${formatMessageDate(message.createdAt)}</div>
          </div>
          <p class="message-body">${escapeHtml(message.message)}</p>
        </article>
      `
    )
    .join("");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function loadMessages() {
  try {
    const response = await fetch(MESSAGES_ENDPOINT, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Unable to load messages");
    }

    const data = await response.json();
    renderMessages(Array.isArray(data.messages) ? data.messages : []);
  } catch (error) {
    messagesList.innerHTML = '<div class="empty-messages">Messages need the memorial server. Run python server.py, then open http://127.0.0.1:8000.</div>';
  }
}

function renderPhotos(photos) {
  if (!photos.length) {
    photosGrid.innerHTML = '<div class="empty-messages">No photos are in the `photos` folder yet. Add image files there and refresh this page.</div>';
    photoStatus.textContent = "Waiting for photos";
    return;
  }

  photosGrid.innerHTML = photos
    .map(
      (photo) => `
        <figure class="photo-card">
          <img src="${photo.url}" alt="${escapeHtml(photo.name)}" loading="lazy">
        </figure>
      `
    )
    .join("");

  photoStatus.textContent = `${photos.length} photo${photos.length === 1 ? "" : "s"} shown`;
}

async function loadPhotos() {
  try {
    const response = await fetch(PHOTOS_ENDPOINT, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error("Unable to load photos");
    }

    const data = await response.json();
    renderPhotos(Array.isArray(data.photos) ? data.photos : []);
  } catch (error) {
    photosGrid.innerHTML = '<div class="empty-messages">Photos need the memorial server too. Run python server.py, then open http://127.0.0.1:8000.</div>';
    photoStatus.textContent = "Gallery unavailable";
  }
}

function createFlyingHearts() {
  const colors = ["#f5b1b7", "#cf5d66", "#ffbf75", "#ffd7a6", "#f08ea1"];

  for (let index = 0; index < 18; index += 1) {
    const heart = document.createElement("span");
    heart.className = "flying-heart";
    heart.style.background = colors[index % colors.length];
    heart.style.left = "50%";
    heart.style.top = "50%";
    heart.style.setProperty("--x", `${Math.round((Math.random() - 0.5) * 520)}px`);
    heart.style.setProperty("--y", `${Math.round(-140 - Math.random() * 360)}px`);
    heart.style.setProperty("--r", `${Math.round((Math.random() - 0.5) * 120)}deg`);
    heart.style.setProperty("--s", (0.75 + Math.random() * 0.9).toFixed(2));
    heart.style.animationDelay = `${Math.round(Math.random() * 180)}ms`;
    heartsLayer.appendChild(heart);

    heart.addEventListener("animationend", () => {
      heart.remove();
    });
  }
}

async function sendThanks() {
  const response = await fetch(API_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw new Error("Unable to save thanks");
  }

  return response.json();
}

async function postMessage(payload) {
  const response = await fetch(MESSAGES_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error("Unable to post message");
  }

  return response.json();
}

heartButton.addEventListener("click", async () => {
  const alreadyClicked = localStorage.getItem(CLICKED_KEY) === "true";
  createFlyingHearts();
  heartButton.disabled = true;

  if (alreadyClicked) {
    buttonNote.textContent = "You already sent thanks from this browser. George is remembered.";
    heartButton.disabled = false;
  } else {
    buttonNote.textContent = "Sharing your thanks...";

    try {
      const data = await sendThanks();
      localStorage.setItem(CLICKED_KEY, "true");
      thanksCount.textContent = Number(data.count || 0).toLocaleString();
      buttonNote.textContent = "Thank you for honoring George Pappas.";
    } catch (error) {
      buttonNote.textContent = "The live counter is unavailable right now. Please try again.";
    } finally {
      heartButton.disabled = false;
    }
  }

  heartButton.classList.remove("pulse");
  void heartButton.offsetWidth;
  heartButton.classList.add("pulse");
});

messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const name = messageName.value.trim();
  const message = messageText.value.trim();

  if (!name || !message) {
    messageStatus.textContent = "Please add your name and a message before posting.";
    return;
  }

  messageSubmit.disabled = true;
  messageStatus.textContent = "Posting your message...";

  try {
    const data = await postMessage({ name, message });
    renderMessages(Array.isArray(data.messages) ? data.messages : []);
    messageForm.reset();
    messageStatus.textContent = "Your message has been added with love.";
  } catch (error) {
    messageStatus.textContent = "The message board is unavailable right now. Please try again.";
  } finally {
    messageSubmit.disabled = false;
  }
});

candleButton.addEventListener("click", () => {
  candleButton.classList.toggle("is-lit");
  const lit = candleButton.classList.contains("is-lit");
  localStorage.setItem(CANDLE_KEY, lit ? "true" : "false");
  candleNote.textContent = lit
    ? "A candle is glowing in memory of George."
    : "A quiet light in loving memory.";
  createFlyingHearts();
});

copyServerCommand.addEventListener("click", copyStartCommandToClipboard);

if (localStorage.getItem(CANDLE_KEY) === "true") {
  candleButton.classList.add("is-lit");
  candleNote.textContent = "A candle is glowing in memory of George.";
}

loadCount();
loadPhotos();
loadMessages();
startRotatingQuotes();
