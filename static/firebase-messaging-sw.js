
// firebase-messaging-sw.js

importScripts('https://www.gstatic.com/firebasejs/9.23.0/firebase-app-compat.js');
importScripts('https://www.gstatic.com/firebasejs/9.23.0/firebase-messaging-compat.js');

// 🔹 Firebase config (same as fcm.js)
firebase.initializeApp({
  apiKey: "AIzaSyBhg-9L1n5iKsOhvtmPwH8iSm-DWgkc2wg",
  authDomain: "tea-application-ac2c1.firebaseapp.com",
  projectId: "tea-application-ac2c1",
  storageBucket: "tea-application-ac2c1.firebasestorage.app",
  messagingSenderId: "260284245568",
  appId: "1:260284245568:web:b031fc17c5a6480663e1a5",
  measurementId: "G-EG6WN4TE02"
});

const messaging = firebase.messaging();

// 🔔 Background notifications
messaging.onBackgroundMessage(payload => {
  self.registration.showNotification(
    payload.notification?.title || "New Order",
    {
      body: payload.notification?.body || "",
      icon: "/static/icon.png"
    }
  );
});

// 🔥 CRITICAL FIX — ALWAYS FORWARD FETCH
self.addEventListener("fetch", event => {
  event.respondWith(fetch(event.request));
});










