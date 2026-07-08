// pages/manage/manage.js
const app = getApp()

const DEFAULT_THRESHOLDS = { cpu: 80, mem: 80, disk: 85, tcp: 5000, webhook: '' }

Page({
  data: {
    list: [],
    searchKey: '',
    loading: false,
    editMode: false,
    showAddModal: false,
    addForm: { host: '', name: '', group: '', sshUser: 'root', sshPassword: '', sshPort: 22 },
    showThresholdModal: false,
    thresholdForm: { host: '', name: '', cpu: 80, mem: 80, disk: 85, tcp: 5000, webhook: '' },
    showImportModal: false,
    importText: '',
    showDeleteModal: false,
    deleteTarget: null,
    showConfigModal: false,
    globalWebhook: '',
  },

  onLoad() {
    var token = wx.getStorageSync('token')
    if (!token) { wx.redirectTo({ url: '/pages/login/login' }); return }
    this.load()
  },

  onPullDownRefresh() {
    var self = this
    this.load().then(function() { wx.stopPullDownRefresh() })
  },

  load: function() {
    var self = this
    self.setData({ loading: true })
    // 加载全局配置
    self._loadGlobalConfig()
    // 先获取管理列表
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/servers/manage',
      method: 'GET',
      header: { 'X-Token': wx.getStorageSync('token') || '' },
      success: function(res1) {
        var rawList = []
        if (res1.data && res1.data.code === 200) {
          rawList = (res1.data.data && res1.data.data.servers) || []
          // 兼容旧版直接返回数组
          if (rawList.length === 0 && res1.data.data instanceof Array) {
            rawList = res1.data.data
          }
          if (res1.data.data && res1.data.data.webhook) {
            self.setData({ globalWebhook: res1.data.data.webhook })
          }
        }
        // 再获取状态
        wx.request({
          url: app.globalData.apiBaseUrl + '/api/servers',
          method: 'GET',
          header: { 'X-Token': wx.getStorageSync('token') || '' },
          success: function(res2) {
            if (res2.data && res2.data.code === 200) {
              var statusMap = {}
              var arr2 = res2.data.data || []
              for (var k = 0; k < arr2.length; k++) {
                statusMap[arr2[k].host] = arr2[k].status
              }
              for (var i = 0; i < rawList.length; i++) {
                rawList[i].status = statusMap[rawList[i].host] || ''
              }
            } else {
              for (var j = 0; j < rawList.length; j++) {
                rawList[j].status = ''
              }
            }
            self.setData({ _fullList: rawList, list: self.doFilter(rawList), loading: false })
          },
          fail: function() {
            self.setData({ _fullList: rawList, list: self.doFilter(rawList), loading: false })
          }
        })
      },
      fail: function() {
        self.setData({ loading: false })
      }
    })
  },

  doFilter: function(list) {
    var key = this.data.searchKey.toLowerCase()
    if (!key) return list
    var out = []
    for (var i = 0; i < list.length; i++) {
      var s = list[i]
      if ((s.host && s.host.toLowerCase().indexOf(key) > -1) ||
          (s.name && s.name.toLowerCase().indexOf(key) > -1) ||
          (s.group && s.group.toLowerCase().indexOf(key) > -1)) {
        out.push(s)
      }
    }
    return out
  },

  onSearchInput: function(e) {
    this.setData({ searchKey: e.detail.value })
    this.setData({ list: this.doFilter(this.data._fullList || []) })
  },

  clearSearch: function() {
    this.setData({ searchKey: '' })
    this.setData({ list: this.data._fullList || [] })
  },

  goDetail: function(e) {
    wx.navigateTo({ url: '/pages/detail/detail?host=' + e.currentTarget.dataset.host })
  },

  // ---- 新增/编辑 ----
  showAdd: function() {
    this.setData({ editMode: false, showAddModal: true, addForm: { host: '', name: '', group: '', sshUser: 'root', sshPassword: '', sshPort: 22 } })
  },

  editServer: function(e) {
    var d = e.currentTarget.dataset
    this.setData({
      editMode: true,
      showAddModal: true,
      addForm: {
        host: d.host,
        name: d.name || '',
        group: d.group || '',
        sshUser: d.sshuser || 'root',
        sshPassword: d.sshpassword || '',
        sshPort: d.sshport || 22
      }
    })
  },

  closeAdd: function() {
    this.setData({ showAddModal: false, editMode: false })
  },

  onAddHost: function(e) { this.setData({ 'addForm.host': e.detail.value }) },
  onAddName: function(e) { this.setData({ 'addForm.name': e.detail.value }) },
  onAddGroup: function(e) { this.setData({ 'addForm.group': e.detail.value }) },
  onAddSshUser: function(e) { this.setData({ 'addForm.sshUser': e.detail.value }) },
  onAddSshPassword: function(e) { this.setData({ 'addForm.sshPassword': e.detail.value }) },
  onAddSshPort: function(e) { this.setData({ 'addForm.sshPort': parseInt(e.detail.value) || 22 }) },

  doAdd: function() {
    var self = this
    var form = this.data.addForm
    if (!form.host) { wx.showToast({ title: '请输入IP地址', icon: 'none' }); return }
    var data = {
      host: form.host, name: form.name, group: form.group,
      sshUser: form.sshUser || 'root', sshPassword: form.sshPassword || '', sshPort: parseInt(form.sshPort) || 22
    }
    if (this.data.editMode) {
      data.action = 'update'
    } else {
      data.action = 'add'
    }
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/servers/manage',
      method: 'POST',
      header: { 'Content-Type': 'application/json', 'X-Token': wx.getStorageSync('token') || '' },
      data: data,
      success: function(res) {
        if (res.data && res.data.code === 200) {
          wx.showToast({ title: res.data.msg || (self.data.editMode ? '保存成功' : '新增成功') })
          self.closeAdd()
          self.load()
        } else {
          wx.showToast({ title: (res.data && res.data.msg) || '操作失败', icon: 'none' })
        }
      },
      fail: function() { wx.showToast({ title: '请求失败', icon: 'none' }) }
    })
  },

  // ---- 阈值 ----
  editThreshold: function(e) {
    var host = e.currentTarget.dataset.host
    var name = e.currentTarget.dataset.name
    var s = null
    for (var i = 0; i < this.data.list.length; i++) {
      if (this.data.list[i].host === host) { s = this.data.list[i]; break }
    }
    var th = (s && s.thresholds) ? s.thresholds : {}
    this.setData({
      showThresholdModal: true,
      thresholdForm: {
        host: host, name: name || '',
        cpu: th.cpu || DEFAULT_THRESHOLDS.cpu,
        mem: th.mem || DEFAULT_THRESHOLDS.mem,
        disk: th.disk || DEFAULT_THRESHOLDS.disk,
        tcp: th.tcp || DEFAULT_THRESHOLDS.tcp,
        webhook: th.webhook || '',
      }
    })
  },

  closeThreshold: function() { this.setData({ showThresholdModal: false }) },
  onThCpu: function(e) { this.setData({ 'thresholdForm.cpu': parseInt(e.detail.value) || 0 }) },
  onThMem: function(e) { this.setData({ 'thresholdForm.mem': parseInt(e.detail.value) || 0 }) },
  onThDisk: function(e) { this.setData({ 'thresholdForm.disk': parseInt(e.detail.value) || 0 }) },
  onThTcp: function(e) { this.setData({ 'thresholdForm.tcp': parseInt(e.detail.value) || 0 }) },
  onThWebhook: function(e) { this.setData({ 'thresholdForm.webhook': e.detail.value }) },

  saveThreshold: function() {
    var self = this
    var th = this.data.thresholdForm
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/servers/manage',
      method: 'POST',
      header: { 'Content-Type': 'application/json', 'X-Token': wx.getStorageSync('token') || '' },
      data: { action: 'threshold', host: th.host, thresholds: { cpu: th.cpu, mem: th.mem, disk: th.disk, tcp: th.tcp, webhook: th.webhook } },
      success: function(res) {
        if (res.data && res.data.code === 200) {
          wx.showToast({ title: '保存成功' })
          self.closeThreshold()
          self.load()
        } else {
          wx.showToast({ title: (res.data && res.data.msg) || '保存失败', icon: 'none' })
        }
      },
      fail: function() { wx.showToast({ title: '请求失败', icon: 'none' }) }
    })
  },

  // ---- 导入 ----
  showImport: function() {
    this.setData({ showImportModal: true, importText: '' })
  },

  closeImport: function() { this.setData({ showImportModal: false }) },

  onImportText: function(e) { this.setData({ importText: e.detail.value }) },

  doImport: function() {
    var self = this
    var text = this.data.importText.trim()
    if (!text) { wx.showToast({ title: '请输入服务器信息', icon: 'none' }); return }
    var lines = text.split('\n')
    var servers = []
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i].trim()
      if (!line) continue
      var parts = line.split(',')
      var host = (parts[0] || '').trim()
      if (!host) continue
      servers.push({ host: host, name: (parts[1] || '').trim(), group: (parts[2] || '').trim() })
    }
    if (servers.length === 0) { wx.showToast({ title: '没有有效数据', icon: 'none' }); return }
    wx.showLoading({ title: '导入中...' })
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/servers/manage',
      method: 'POST',
      header: { 'Content-Type': 'application/json', 'X-Token': wx.getStorageSync('token') || '' },
      data: { action: 'import', servers: servers },
      success: function(res) {
        wx.hideLoading()
        if (res.data && res.data.code === 200) {
          wx.showToast({ title: '成功导入 ' + (res.data.count || servers.length) + ' 台' })
          self.closeImport()
          self.load()
        } else {
          wx.showToast({ title: (res.data && res.data.msg) || '导入失败', icon: 'none' })
        }
      },
      fail: function() { wx.hideLoading(); wx.showToast({ title: '请求失败', icon: 'none' }) }
    })
  },

  // ---- 导出 ----
  exportData: function() {
    var self = this
    wx.showLoading({ title: '导出中...' })
    var token = wx.getStorageSync('token') || ''
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/servers/manage',
      method: 'GET',
      header: { 'X-Token': token },
      success: function(res) {
        wx.hideLoading()
        var servers = []
        if (res.data && res.data.code === 200 && res.data.data) {
          if (res.data.data.servers) {
            servers = res.data.data.servers
          } else if (res.data.data instanceof Array) {
            servers = res.data.data
          }
        }
        if (servers.length === 0) {
          wx.showToast({ title: '导出失败', icon: 'none' }); return
        }
        var lines = ['IP,名称,分组,SSH用户,SSH端口']
        for (var i = 0; i < servers.length; i++) {
          var s = servers[i]
          lines.push(s.host + ',' + (s.name || '') + ',' + (s.group || '') + ',' + (s.sshUser || 'root') + ',' + (s.sshPort || 22))
        }
        wx.setClipboardData({ data: lines.join('\n'), success: function() { wx.showToast({ title: '已复制到剪贴板' }) } })
      },
      fail: function() { wx.hideLoading(); wx.showToast({ title: '请求失败', icon: 'none' }) }
    })
  },

  // ---- 删除 ----
  confirmDelete: function(e) {
    this.setData({
      showDeleteModal: true,
      deleteTarget: { host: e.currentTarget.dataset.host, name: e.currentTarget.dataset.name }
    })
  },

  closeDelete: function() { this.setData({ showDeleteModal: false, deleteTarget: null }) },

  doDelete: function() {
    var self = this
    var target = this.data.deleteTarget
    if (!target) return
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/servers/manage',
      method: 'POST',
      header: { 'Content-Type': 'application/json', 'X-Token': wx.getStorageSync('token') || '' },
      data: { action: 'delete', host: target.host },
      success: function(res) {
        if (res.data && res.data.code === 200) {
          wx.showToast({ title: '已删除' })
          self.closeDelete()
          self.load()
        } else {
          wx.showToast({ title: (res.data && res.data.msg) || '删除失败', icon: 'none' })
        }
      },
      fail: function() { wx.showToast({ title: '请求失败', icon: 'none' }) }
    })
  },

  // ---- 全局配置 ----
  showGlobalConfig: function() {
    this.setData({ showConfigModal: true })
  },

  closeGlobalConfig: function() {
    this.setData({ showConfigModal: false })
  },

  onGlobalWebhook: function(e) {
    this.setData({ globalWebhook: e.detail.value })
  },

  _loadGlobalConfig: function() {
    var self = this
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/servers/manage',
      method: 'GET',
      header: { 'Content-Type': 'application/json', 'X-Token': wx.getStorageSync('token') || '' },
      data: {},
      success: function(res) {
        if (res.data && res.data.code === 200 && res.data.data) {
          // 新版 {servers, webhook} 或旧版 []
          var wh = res.data.data.webhook || ''
          self.setData({ globalWebhook: wh })
        }
      },
      fail: function() {}
    })
  },

  saveGlobalConfig: function() {
    var self = this
    var wh = this.data.globalWebhook
    wx.request({
      url: app.globalData.apiBaseUrl + '/api/servers/manage',
      method: 'POST',
      header: { 'Content-Type': 'application/json', 'X-Token': wx.getStorageSync('token') || '' },
      data: { action: 'config', webhook: wh },
      success: function(res) {
        if (res.data && res.data.code === 200) {
          wx.showToast({ title: '配置已保存' })
          self.closeGlobalConfig()
        } else {
          wx.showToast({ title: (res.data && res.data.msg) || '保存失败', icon: 'none' })
        }
      },
      fail: function() { wx.showToast({ title: '请求失败', icon: 'none' }) }
    })
  },
})
