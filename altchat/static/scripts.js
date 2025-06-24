const socket = io();

const form = document.getElementById('chat-form');
const input = document.getElementById('m');
const messages = document.getElementById('messages');
const userList = document.getElementById('user-list');
const altToggle = document.getElementById('alt-toggle');
const muteToggle = document.getElementById('mute-toggle');

let unreadCount = 0;

function updateTitle() {
  if (unreadCount > 0) {
    document.title = `(${unreadCount}) Neue Nachricht – ALTCHAT`;
  } else {
    document.title = 'ALTCHAT';
  }
}

socket.on('chat_message', data => {
  if (!muteToggle.checked) {
    const item = document.createElement('div');
    item.style.color = data.color;
    item.textContent = `[${data.user}] ${data.text}`;
    messages.appendChild(item);
    messages.scrollTop = messages.scrollHeight;
    if (document.hidden) {
      unreadCount++;
      updateTitle();
    }
  }
});

socket.on('direct_message', data => {
  const item = document.createElement('div');
  item.style.color = '#00ffff';
  item.textContent = `(DM from ${data.from}) ${data.text}`;
  messages.appendChild(item);
  messages.scrollTop = messages.scrollHeight;
  if (document.hidden) {
    unreadCount++;
    updateTitle();
  }
});

socket.on('user_list', users => {
  userList.innerHTML = '';
  users.forEach(u => {
    const li = document.createElement('li');
    li.textContent = u;
    li.addEventListener('click', () => {
      window.location.href = `/dm/${u}`;
    });
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

document.addEventListener('visibilitychange', () => {
  if (!document.hidden) {
    unreadCount = 0;
    updateTitle();
  }
});
