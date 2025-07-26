self.addEventListener('push', function(event) {
  const data = event.data.json();
  const title = data.title;
  const options = {
    body: data.body,
    icon: '/static/icon.png'
  };
  event.waitUntil(self.registration.showNotification(title, options));
});
