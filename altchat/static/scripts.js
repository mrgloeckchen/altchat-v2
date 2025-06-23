const socket = io();

const form = document.getElementById('chat-form');
const input = document.getElementById('m');
const messages = document.getElementById('messages');
const userList = document.getElementById('user-list');
const altToggle = document.getElementById('alt-toggle');

socket.on('chat_message', data => {
  const item = document.createElement('div');
  item.style.color = data.color;
  item.textContent = `[${data.user}] ${data.text}`;
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
});

socket.on('user_list', users => {
  userList.innerHTML = '';
  users.forEach(u => {
    const li = document.createElement('li');
    li.textContent = u;
    userList.appendChild(li);
  });
});

form.addEventListener('submit', e => {
  e.preventDefault();
  if (input.value) {
    socket.emit('chat_message', {text: input.value, alt: altToggle.checked});
    input.value = '';
  }
});
