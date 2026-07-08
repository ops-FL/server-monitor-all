// pages/index/index.js
const app = getApp()

Page({
  data: { list: [], total: 0, alive: 0, dead: 0, alerts: 0, filter: '' },

  onLoad() {
    this._mockData = null
    this._checkLogin()
  },

  _checkLogin() {
    const token = wx.getStorageSync('token')
    if (!token) {
      wx.redirectTo({ url: '/pages/login/login' })
      return
    }
    this.load()
  },

  onPullDownRefresh() {
    this.load().then(() => wx.stopPullDownRefresh())
  },

  async load() {
    const res = await app.request('/api/servers')
    if (res && res.code === 200 && res.data) {
      this.recalc(res.data)
    } else {
      if (!this._mockData) {
        const list = []
        for (let i = 1; i <= 100; i++) {
          const st = ['alive', 'alive', 'alive', 'alive', 'slow', 'dead'][i % 6]
          list.push({
            host: '10.0.' + Math.floor(i / 50) + '.' + (i % 256),
            name: 'server-' + String(i).padStart(3, '0'),
            status: st,
            cpu: +(Math.random() * 100).toFixed(1),
            mem: +(20 + Math.random() * 80).toFixed(1),
            disk: +(10 + Math.random() * 90).toFixed(1),
            tcp: Math.floor(Math.random() * 8000),
            disks: [],
            lastUpdate: '刚刚',
          })
        }
        this._mockData = list
      }
      this.recalc(this._mockData)
    }
    // 加载告警统计（含离线）
    this._loadAlertCount()
  },

  _loadAlertCount: function() {
    var self = this
    var token = wx.getStorageSync('token') || ''
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/alerts',
      method: 'GET',
      header: { 'X-Token': token },
      success: function(res) {
        if (res.data && res.data.code === 200 && res.data.data) {
          var d = res.data.data
          var totalAlerts = d.alerts ? d.alerts.length : 0
          self.setData({ alerts: totalAlerts })
        }
      },
      fail: function() {}
    })
  },

  _isAlert: function(s) {
    if (s.cpu > 80) return true
    if (s.mem > 80) return true
    // 磁盘告警：优先看disks分区数组，有分区数据则遍历分区
    if (s.disks && s.disks.length > 0) {
      if (s.disks.some(function(d) { return d.percent > 85 })) return true
    } else if (s.disk > 85) {
      return true
    }
    if (s.tcp > 5000) return true
    return false
  },

  recalc(all) {
    var self = this
    this.setData({
      _all: all,
      list: this._filter(all),
      total: all.length,
      alive: all.filter(function(s) { return s.status === 'alive' }).length,
      dead: all.filter(function(s) { return s.status === 'dead' }).length,
      alerts: all.filter(function(s) { return self._isAlert(s) }).length,
    })
  },

  _filter(all) {
    var f = this.data.filter
    if (!f) return all
    if (f === 'dead') return all.filter(function(s) { return s.status === 'dead' })
    if (f === 'cpu') return all.filter(function(s) { return s.cpu > 80 })
    if (f === 'mem') return all.filter(function(s) { return s.mem > 80 })
    if (f === 'disk') return all.filter(function(s) {
      if (s.disks && s.disks.length > 0) {
        return s.disks.some(function(d) { return d.percent > 85 })
      }
      return s.disk > 85
    })
    if (f === 'tcp') return all.filter(function(s) { return s.tcp > 5000 })
    return all
  },

  setFilter(e) {
    var f = e.currentTarget.dataset.f
    this.setData({ filter: f })
    this.setData({ list: this._filter(this.data._all || this.data.list) })
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/detail/detail?host=' + e.currentTarget.dataset.host })
  },

  goAlert() {
    wx.navigateTo({ url: '/pages/alerts/alerts' })
  },

  goManage() {
    wx.navigateTo({ url: '/pages/manage/manage' })
  },
})
