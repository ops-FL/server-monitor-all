// app.js
App({
  globalData: {
    apiBaseUrl: 'http://192.168.0.1:9098'
  },

  request(url, data = {}, method = 'GET') {
    const base = this.globalData.apiBaseUrl
    const token = wx.getStorageSync('token')

    return new Promise((resolve) => {
      wx.request({
        url: base + url,
        data,
        method,
        header: {
          'Content-Type': 'application/json',
          'X-Token': token || '',
        },
        timeout: 10000,
        success: res => {
          // token 失效或未登录，跳回登录页
          if (res.data && res.data.code === 401) {
            wx.removeStorageSync('token')
            wx.redirectTo({ url: '/pages/login/login' })
            resolve(null)
            return
          }
          resolve(res.data)
        },
        fail: () => resolve(null)
      })
    })
  },

  onLaunch() {
    const token = wx.getStorageSync('token')
    if (!token) {
      wx.redirectTo({ url: '/pages/login/login' })
    }
  }
})
