import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import 'ant-design-vue/dist/reset.css'
import './assets/main.css'
import { installGlobalErrorHandler } from './utils/globalErrorHandler.js'

const app = createApp(App)

app.use(createPinia())
installGlobalErrorHandler(app)
app.mount('#app')
