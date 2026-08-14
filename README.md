---
title: RS Video Encoder Bot
emoji: 🎬
colorFrom: red
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# RS Video Encoder Bot

A Telegram bot for compressing/encoding videos. Runs as a background
worker; the web port (7860) only serves a small status page so Hugging
Face Spaces can confirm the container started -- all real interaction
happens through Telegram.
