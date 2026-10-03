const orbButton = document.querySelector('#orbButton');
const statusText = document.querySelector('#status');
const answerText = document.querySelector('#answer');
const questionForm = document.querySelector('#questionForm');
const questionInput = document.querySelector('#questionInput');

let isListening = false;

orbButton.addEventListener('click', () => {
  if (isListening) {
    return;
  } else {
    startListening();
  }
});

async function startListening() {
  isListening = true;
  orbButton.classList.add('is-listening');
  statusText.textContent = 'Listening...';
  try {
    const response = await fetch('/listen', { method: 'POST' });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Microphone is unavailable.');
    if (data.question) await ask(data.question);
  } catch (error) {
    statusText.textContent = error.message;
    questionInput.focus();
  } finally {
    isListening = false;
    orbButton.classList.remove('is-listening');
  }
}

questionForm.addEventListener('submit', (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (question) ask(question);
});

async function ask(question) {
  questionInput.value = '';
  answerText.textContent = '';
  statusText.textContent = 'Thinking...';
  orbButton.classList.add('is-speaking');

  try {
    const response = await fetch('/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || 'Request failed');
    answerText.textContent = data.answer;
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(data.answer));
    }
    statusText.textContent = 'Ready for another question';
  } catch (error) {
    answerText.textContent = error.message;
    statusText.textContent = 'The assistant is offline';
  } finally {
    orbButton.classList.remove('is-speaking');
  }
}
