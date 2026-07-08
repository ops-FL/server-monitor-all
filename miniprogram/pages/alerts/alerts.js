const app = getApp()

// 类型映射
const TYPE_MAP = { cpu: 'CPU', mem: '内存', disk: '磁盘', tcp: 'TCP' }

Page({
  data: { alerts: [], summary: {}, filterType: '' },

  onLoad(opt) {
    this._filterType = (opt && opt.type && TYPE_MAP[opt.type]) || ''
    this.setData({ filterType: this._filterType })
    this.load()
  },

  onShow() {
    this.load()
  },

  load: function() {
    var self = this
    var ft = this._filterType
    var token = wx.getStorageSync('token') || ''
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/alerts',
      method: 'GET',
      header: { 'X-Token': token },
      success: function(res) {
        if (res.data && res.data.code === 200 && res.data.data) {
          self._show(res.data.data.alerts, res.data.data)
        } else {
          self._useMock()
        }
      },
      fail: function() { self._useMock() }
    })
  },

  _useMock: function() {
    var summary = { cpuAlerts: 0, memAlerts: 0, diskAlerts: 0, tcpAlerts: 0, offlineAlerts: 0 }
    var alerts = []
    for (var i = 1; i <= 100; i++) {
      var cpu = +(Math.random() * 100).toFixed(1)
      var mem = +(20 + Math.random() * 80).toFixed(1)
      var disk = +(10 + Math.random() * 90).toFixed(1)
      var tcp = Math.floor(Math.random() * 8000)
      var host = '10.0.' + Math.floor(i / 50) + '.' + (i % 256)
      var name = 'server-' + String(i).padStart(3, '0')
      if (cpu > 80) {
        alerts.push({ host: host, name: name, type: 'CPU', desc: 'CPU高', value: cpu.toFixed(0) + '%', time: '刚刚' })
        summary.cpuAlerts++
      }
      if (mem > 80) {
        alerts.push({ host: host, name: name, type: '内存', desc: '内存高', value: mem.toFixed(0) + '%', time: '刚刚' })
        summary.memAlerts++
      }
      if (disk > 85) {
        alerts.push({ host: host, name: name, type: '磁盘', desc: '磁盘满', value: disk.toFixed(1) + '%', mount: '/', used: '86.0GB', total: '94.0GB', time: '刚刚' })
        summary.diskAlerts++
      }
      if (tcp > 5000) {
        alerts.push({ host: host, name: name, type: 'TCP', desc: '连接数过多', value: String(tcp), time: '刚刚' })
        summary.tcpAlerts++
      }
    }
    this._show(alerts, summary)
  },

  _show(allAlerts, summary) {
    const ft = this._filterType
    const alerts = ft ? allAlerts.filter(function(a) { return a.type === ft }) : allAlerts
    this.setData({ alerts, summary })
  },

  switchType(e) {
    this._filterType = e.currentTarget.dataset.type || ''
    this.setData({ filterType: this._filterType })
    this.load()
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/detail/detail?host=' + e.currentTarget.dataset.host })
  },
})
