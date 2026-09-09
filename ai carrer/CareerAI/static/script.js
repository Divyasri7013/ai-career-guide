const careerForm = document.querySelector("#career-form");
const resumeForm = document.querySelector("#resume-form");
const resumeFile = document.querySelector("#resume-file");
const fileName = document.querySelector("#file-name");

function showStatus(element, message, type = "") {
  element.textContent = message;
  element.className = `form-status ${type}`;
}

function displayResult(container, text) {
  container.innerHTML = "";
  const content = document.createElement("div");
  content.className = "result-content";
  content.textContent = text;
  container.appendChild(content);
}

async function readError(response) {
  try {
    const data = await response.json();
    return data.error || "Something went wrong. Please try again.";
  } catch (_error) {
    return "The server returned an unexpected response.";
  }
}

careerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.querySelector("#career-status");
  const result = document.querySelector("#career-result");
  const formData = new FormData(careerForm);
  const data = Object.fromEntries(formData.entries());
  showStatus(status, "🤖 AI is analyzing your profile...", "loading");

  try {
    const response = await fetch("/career", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error(await readError(response));
    const payload = await response.json();
    displayResult(result, payload.result);
    showStatus(status, "Your personalized guidance is ready.");
  } catch (error) {
    showStatus(status, error.message || "Network error. Please try again.", "error");
  }
});

resumeFile.addEventListener("change", () => {
  fileName.textContent = resumeFile.files[0]?.name || "Drop your resume here";
});

resumeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const status = document.querySelector("#resume-status");
  const result = document.querySelector("#resume-result");
  const formData = new FormData(resumeForm);
  showStatus(status, "📄 AI is analyzing your resume...", "loading");

  try {
    const response = await fetch("/resume", { method: "POST", body: formData });
    if (!response.ok) throw new Error(await readError(response));
    const payload = await response.json();
    displayResult(result, payload.result);
    showStatus(status, "Your resume review is ready.");
  } catch (error) {
    showStatus(status, error.message || "Network error. Please try again.", "error");
  }
});
