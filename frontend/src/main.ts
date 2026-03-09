import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

import 'tailwindcss/theme.css'
import 'tailwindcss/utilities.css'
import './styles/glassmorphism.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')
