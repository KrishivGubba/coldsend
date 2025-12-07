const API_URL = "http://localhost:3000";

document.addEventListener('DOMContentLoaded', () => {
  const saveBtn = document.getElementById('saveBtn');
  saveBtn.addEventListener('click', saveSettings);
});

function saveSettings() {
  const userName = document.getElementById('userName').value.trim();
  const userAbout = document.getElementById('userAbout').value.trim();
  const apiKey = document.getElementById('apiKey').value.trim();
  const signatureHtml = document.getElementById('signatureHtml').value.trim();
  const resumePath = document.getElementById('resumePath').value.trim();

  // Save to chrome storage
  chrome.storage.local.set({
    userName: userName,
    userAbout: userAbout,
    apiKey: apiKey,
    signatureHtml: signatureHtml,
    resumePath: resumePath
  });

  // Send to backend server
  fetch(`${API_URL}/save-settings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      userName: userName,
      userAbout: userAbout,
      apiKey: apiKey,
      signatureHtml: signatureHtml,
      resumePath: resumePath
    })
  })
  .then(response => response.json())
  .then(data => {
    if (data.success) {
      showSuccessMessage();
    } else {
      alert("Error saving settings to server");
    }
  })
  .catch(err => {
    console.error("Error saving settings:", err);
    alert("Error: Make sure the Flask server is running on localhost:3000");
  });
}

function showSuccessMessage() {
  const card = document.querySelector('.card');
  card.innerHTML = `
    <div class="wave">✅</div>
    <h1>You're all set!</h1>
    <p class="subtitle">Settings saved successfully.</p>
  `;
}



function displaySignaturePreview() {
  const signatureHtml = document.getElementById('signatureHtml').value.trim();
  const signaturePreview = document.getElementById('signaturePreview');
  signaturePreview.innerHTML = signatureHtml;
}

document.getElementById('signatureHtml').addEventListener('input', displaySignaturePreview);