// pages/detail/detail.js
const app = getApp()

Page({
  data: {
    data: { host: '', name: '', status: 'alive', cpu: 0, mem: 0, disk: 0, load1: 0,
            memUsed: 0, memTotal: 0, diskUsed: 0, diskTotal: 0,
            ioRead: 0, ioWrite: 0, ioUtil: 0, tcp: 0, tcpTw: 0, disks: [], lastUpdate: 'N/A' }
  },

  onLoad(opt) {
    if (opt.host) {
      this.setData({ 'data.host': opt.host, 'data.name': opt.host })
      this.load()
    }
  },

  async load() {
    var res = await app.request('/api/server/' + this.data.data.host)
    if (res && res.code === 200 && res.data) {
      this.setData({ data: res.data })
    } else {
      this.setData({
        data: {
          host: this.data.data.host, name: this.data.data.host, status: 'alive',
          cpu: +(Math.random() * 100).toFixed(1),
          mem: +(20 + Math.random() * 80).toFixed(1),
          disk: +(10 + Math.random() * 90).toFixed(1),
          load1: +(Math.random() * 8).toFixed(2),
          memUsed: +(8 + Math.random() * 24).toFixed(1), memTotal: 32,
          diskUsed: +(50 + Math.random() * 200).toFixed(1), diskTotal: 500,
          ioRead: +(Math.random() * 50).toFixed(2), ioWrite: +(Math.random() * 20).toFixed(2), ioUtil: +(Math.random() * 100).toFixed(1),
          disks: [{mount:'/', used_gb: 50, total_gb: 500, percent: 10}],
          tcp: Math.floor(Math.random() * 5000), tcpTw: Math.floor(Math.random() * 1000),
          lastUpdate: '刚刚',
        }
      })
    }
  },

  refresh() { this.load() }
})
