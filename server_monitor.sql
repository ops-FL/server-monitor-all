/*
 Navicat Premium Dump SQL

 Source Server         : 测试数据库
 Source Server Type    : MySQL
 Source Server Version : 50736 (5.7.36-log)
 Source Host           : 0.0.0.0:3306
 Source Schema         : server_monitor

 Target Server Type    : MySQL
 Target Server Version : 50736 (5.7.36-log)
 File Encoding         : 65001

 Date: 08/07/2026 10:45:16
*/

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- ----------------------------
-- Table structure for app_config
-- ----------------------------
DROP TABLE IF EXISTS `app_config`;
CREATE TABLE `app_config`  (
  `key` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `value` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL,
  PRIMARY KEY (`key`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;
-- ============================================================================
-- 可选：插入默认配置
-- ============================================================================
-- INSERT INTO app_config (`key`, `value`) VALUES ('webhook_url', 'https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的KEY');

-- ----------------------------
-- Table structure for metrics
-- ----------------------------
DROP TABLE IF EXISTS `metrics`;
CREATE TABLE `metrics`  (
  `id` bigint(20) NOT NULL AUTO_INCREMENT,
  `server_id` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `ts` double NOT NULL,
  `cpu_percent` double NULL DEFAULT NULL,
  `mem_percent` double NULL DEFAULT NULL,
  `disk_percent` double NULL DEFAULT NULL,
  `mem_total_mb` double NULL DEFAULT NULL,
  `mem_used_mb` double NULL DEFAULT NULL,
  `disk_total_gb` double NULL DEFAULT NULL,
  `disk_used_gb` double NULL DEFAULT NULL,
  `disk_read_bytes` double NULL DEFAULT NULL,
  `disk_write_bytes` double NULL DEFAULT NULL,
  `tcp_established` int(11) NULL DEFAULT NULL,
  `tcp_time_wait` int(11) NULL DEFAULT NULL,
  `load_1m` double NULL DEFAULT NULL,
  `load_5m` double NULL DEFAULT NULL,
  `load_15m` double NULL DEFAULT NULL,
  `disks_json` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL,
  PRIMARY KEY (`id`) USING BTREE,
  UNIQUE INDEX `uk_server_ts`(`server_id`, `ts`) USING BTREE,
  INDEX `idx_ts`(`ts`) USING BTREE
) ENGINE = InnoDB AUTO_INCREMENT = 1980 CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

-- ----------------------------
-- Table structure for servers
-- ----------------------------
DROP TABLE IF EXISTS `servers`;
CREATE TABLE `servers`  (
  `host` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NOT NULL,
  `name` varchar(128) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT NULL,
  `group_name` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT 'default',
  `port` int(11) NULL DEFAULT 22,
  `thresholds_json` text CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL COMMENT '告警阈值配置(JSON)',
  `ssh_user` varchar(64) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT 'root' COMMENT 'SSH用户',
  `ssh_password` varchar(256) CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci NULL DEFAULT '' COMMENT 'SSH密码',
  `ssh_port` int(11) NULL DEFAULT 22 COMMENT 'SSH端口',
  PRIMARY KEY (`host`) USING BTREE
) ENGINE = InnoDB CHARACTER SET = utf8mb4 COLLATE = utf8mb4_general_ci ROW_FORMAT = Dynamic;

SET FOREIGN_KEY_CHECKS = 1;
