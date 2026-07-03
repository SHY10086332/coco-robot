// ============================================================
// Coco 导购机器人 — 3D 外观 v5 (立式)
// 总高 ~900mm，可放地面对话
// 熊出没可爱风格，蛋形机身，200mm圆屏面部
// 按 F5 预览，F6 渲染导出 STL
// ============================================================
$fn = 120;

// ===== Toggle =====
SHOW_ARMS = true;

// ===== 核心尺寸（mm）v5 立式 =====
SCREEN_D   = 200;   // 圆屏直径 — 不变，复用
BODY_W     = 280;   // 机身底部宽度
BODY_TOP_W = 220;   // 机身顶部宽度
BODY_H     = 600;   // 机身高度 (v4:300 → v5:600)
BODY_D     = 220;   // 机身深度

TRACK_W    = 250;   // 履带中心距 (v4:220 → v5:250)
TRACK_L    = 290;   // 履带接地长度 (v4:270 → v5:290)
WHEEL_R    = 35;    // 驱动轮半径 — 不变

NECK_H     = 25;    // 脖子过渡
HEAD_H     = 110;   // 头部后壳高度
SCREEN_TILT = 28;   // 屏幕仰角(°)，立式机器低头看屏的最佳角度

// 3D打印分段位置（从底部算起的高度）
PRINT_SEG1_H = 210;  // 下段高度
PRINT_SEG2_H = 210;  // 中段高度
// 上段 = BODY_H - 210 - 210 = 180mm

// ===== 颜色 =====
C_WHITE    = "#F7F8FA";
C_BLUE     = "#4A90D9";
C_BLUE_DK  = "#2C5F8A";
C_CYAN     = "#00FFD0";
C_SCREEN   = "#0A0C12";
C_GRAY     = "#3A3C42";
C_DK_GRAY  = "#25272B";
C_TRACK    = "#1A1C20";
C_SILVER   = "#D0D4DC";
C_GOLD     = "#FFD700";
C_RED      = "#FF6B35";
C_SENSOR   = "#333538";


// ==================== 辅助模块 ====================

module ring(r, h, t) {
    difference() {
        cylinder(r=r, h=h, center=true);
        cylinder(r=r-t, h=h+2, center=true);
    }
}


// ==================== 履带底盘 ====================

module track_tread(side) {
    sx = side * TRACK_W/2;
    tw = 28;
    l = TRACK_L + WHEEL_R*2 + 10;

    translate([sx, 0, WHEEL_R + 14])
    rotate([0, 90, 0])
    color(C_TRACK) {
        difference() {
            hull() {
                translate([0,  l/2, 0]) cylinder(r=WHEEL_R+6, h=tw);
                translate([0, -l/2, 0]) cylinder(r=WHEEL_R+6, h=tw);
            }
            hull() {
                translate([0,  l/2, 0]) cylinder(r=WHEEL_R-2, h=tw+4);
                translate([0, -l/2, 0]) cylinder(r=WHEEL_R-2, h=tw+4);
            }
        }
        for(i=[0:18]) {
            translate([0, -l/2 + i*l/18, 0])
            rotate([90, 0, 90])
                cube([tw+1, 3, 3], center=true);
        }
    }
}

module drive_wheel(side, fb) {
    sx = side * TRACK_W/2;
    sy = fb * TRACK_L/2;
    z = WHEEL_R + 14;

    translate([sx, sy, z])
    rotate([0, 90, 0]) {
        color("#1a1a1a")
        difference() {
            cylinder(r=WHEEL_R+3, h=12, center=true);
            cylinder(r=WHEEL_R-3, h=14, center=true);
        }
        color(C_DK_GRAY)
        difference() {
            cylinder(r=WHEEL_R-3, h=10, center=true);
            for(i=[0:5])
                rotate([0, 0, i*60])
                    translate([WHEEL_R*0.5, 0, 0])
                        cylinder(r=WHEEL_R*0.18, h=12, center=true);
        }
        color(C_SILVER)
        cylinder(r=6, h=8, center=true);
    }
}

module track_chassis() {
    cw = TRACK_W + 90;   // 340mm 总宽
    cl = TRACK_L + 50;   // 340mm 总长
    ch = 55;

    // 底盘基座
    color(C_DK_GRAY)
    translate([0, 0, 4])
    hull() {
        for(x=[-1,1], y=[-1,1])
            translate([x*(cw/2-16), y*(cl/2-16), 0])
                cylinder(r=16, h=ch);
    }

    // 上面板
    color("#303338")
    translate([0, 0, ch + 3])
    hull() {
        for(x=[-1,1], y=[-1,1])
            translate([x*(cw/2-28), y*(cl/2-28), 0])
                cylinder(r=8, h=4);
    }

    // 两侧履带
    for(side=[-1, 1]) {
        track_tread(side);
        drive_wheel(side, 1);
        drive_wheel(side, -1);

        color(C_GRAY)
        translate([side * TRACK_W/2, 0, WHEEL_R + 14])
        rotate([0, 90, 0])
        hull() {
            translate([0,  TRACK_L/2 + WHEEL_R*0.3, 0])
                cylinder(r=WHEEL_R+7, h=18);
            translate([0, -TRACK_L/2 - WHEEL_R*0.3, 0])
                cylinder(r=WHEEL_R+7, h=18);
        }
    }

    // 前后防撞条
    for(fb=[-1, 1])
    color("#2a2c30")
    translate([0, fb*(cl/2 - 8), ch/2])
    rotate([90, 0, 0])
    hull() {
        translate([-cw/2+20, 0, 0]) cylinder(r=6, h=10, center=true);
        translate([ cw/2-20, 0, 0]) cylinder(r=6, h=10, center=true);
    }
}


// ==================== 机身主体 ====================

module body_segment(z_start, seg_h, bw_bottom, bw_top) {
    // 通用蛋形机身段，上下直径不同
    color(C_WHITE)
    translate([0, 0, z_start])
    difference() {
        hull() {
            translate([0, 0, 0])
                scale([1, BODY_D/BODY_W, 1])
                    cylinder(r=bw_bottom/2, h=3);
            translate([0, 0, seg_h - 3])
                scale([1, BODY_D/BODY_W, 1])
                    cylinder(r=bw_top/2, h=3);
        }
        // 正面切平
        translate([BODY_W/2 - 15, -BODY_D, -5])
            cube([40, BODY_D*2, seg_h + 30]);
    }
}

module body_main() {
    bw_bot = BODY_W;
    bw_top = BODY_TOP_W;
    bz = 60;

    // 完整蛋形主体
    color(C_WHITE)
    translate([0, 0, bz])
    difference() {
        hull() {
            // 底部宽
            translate([0, 0, 0])
                scale([1, BODY_D/BODY_W, 1])
                    cylinder(r=bw_bot/2, h=8);
            // 中部最宽
            translate([0, 0, BODY_H*0.30])
                scale([1, BODY_D/BODY_W, 1])
                    cylinder(r=bw_bot/2 + 8, h=8);
            // 上部收窄
            translate([0, 0, BODY_H*0.65])
                scale([1, BODY_D/BODY_W, 1])
                    cylinder(r=(bw_bot + bw_top)/4 + 5, h=8);
            // 顶部
            translate([0, 0, BODY_H - 10])
                scale([1, BODY_D/BODY_W, 1])
                    cylinder(r=bw_top/2, h=10);
        }
        // 正面切平
        translate([bw_bot/2 - 15, -BODY_D, -5])
            cube([40, BODY_D*2, BODY_H + 30]);
    }

    // 正面屏幕凹陷区域（容纳倾斜屏幕）
    sr = SCREEN_D / 2;
    color("#EBEDF2")
    translate([bw_bot/2 - 18, 0, bz + BODY_H*0.38])
    rotate([0, -90, 0])
    rotate([SCREEN_TILT, 0, 0]) {
        // 比屏幕外框大一圈的凹陷
        translate([0, 0, -3])
        cylinder(r=sr + 22, h=8);
        // 底部加宽（屏幕倾斜后底部会突出一些）
        translate([0, -sr*0.15, -2])
        scale([1, 0.5, 1])
        cylinder(r=sr + 18, h=7);
    }

    // === 装饰环（兼做3D打印分段标记）===

    // 底部环
    color(C_BLUE)
    translate([0, 0, bz + BODY_H - 22])
    scale([1, BODY_D/BODY_W, 1])
    ring(r=bw_bot/2 + 5, h=10, t=4);

    // 顶部环
    color(C_BLUE)
    translate([0, 0, bz + 8])
    scale([1, BODY_D/BODY_W, 1])
    ring(r=bw_bot/2 + 5, h=10, t=4);

    // 分段标记环（下段顶部 / 中段底部）
    color(C_BLUE)
    translate([0, 0, bz + PRINT_SEG1_H])
    scale([1, BODY_D/BODY_W, 1])
    ring(r=(bw_bot + bw_top)/4 + 12, h=5, t=2.5);

    // 分段标记环（中段顶部 / 上段底部）
    color(C_BLUE)
    translate([0, 0, bz + PRINT_SEG1_H + PRINT_SEG2_H])
    scale([1, BODY_D/BODY_W, 1])
    ring(r=(bw_bot + bw_top)/4 + 6, h=5, t=2.5);
}


// ==================== 蝴蝶结 ====================

module bow_tie() {
    bw_bot = BODY_W;
    bz = 60;

    translate([bw_bot/2 - 30, 0, bz + BODY_H*0.58])
    color(C_BLUE_DK) {
        translate([-22, 0, 0])
        rotate([0, 15, 0])
        scale([1, 1.5, 0.6])
            sphere(r=18);
        translate([22, 0, 0])
        rotate([0, -15, 0])
        scale([1, 1.5, 0.6])
            sphere(r=18);
        sphere(r=12);
        translate([0, 0, -8])
        rotate([10, 0, 0]) {
            translate([-6, 2, -12])
            rotate([0, 30, 0])
            scale([0.4, 0.8, 0.3])
                sphere(r=18);
            translate([6, 2, -12])
            rotate([0, -30, 0])
            scale([0.4, 0.8, 0.3])
                sphere(r=18);
        }
    }
}


// ==================== 屏幕面板 ====================

module screen_bezel() {
    sr = SCREEN_D / 2;
    bw_bot = BODY_W;
    bz = 60;

    translate([bw_bot/2 - 16, 0, bz + BODY_H*0.38])
    rotate([0, -90, 0])
    rotate([SCREEN_TILT, 0, 0]) {
        color(C_SILVER)
        difference() {
            cylinder(r=sr + 18, h=10);
            translate([0, 0, -1]) cylinder(r=sr + 6, h=12);
        }
        color("#B8BCC4")
        translate([0, 0, 10])
        difference() {
            cylinder(r=sr + 6, h=3);
            translate([0, 0, -1]) cylinder(r=sr - 2, h=5);
        }
        color("#1A1C20")
        translate([0, 0, 13])
        ring(r=sr + 1, h=2, t=3);
    }
}

module screen_display() {
    sr = SCREEN_D / 2;
    bw_bot = BODY_W;
    bz = 60;

    translate([bw_bot/2 - 16, 0, bz + BODY_H*0.38])
    rotate([0, -90, 0])
    rotate([SCREEN_TILT, 0, 0]) {
        color(C_SCREEN)
        translate([0, 0, 15])
        cylinder(r=sr, h=1.5);

        eye_r = sr * 0.25;
        for(ex=[-1, 1])
        color(C_CYAN)
        translate([ex * sr*0.32, sr*0.08, 16.5])
        scale([1, 1.25, 1])
            cylinder(r=eye_r, h=1);

        for(ex=[-1, 1])
        color("#0A0C12")
        translate([ex * sr*0.32, sr*0.06, 17.5])
            cylinder(r=eye_r * 0.35, h=1);

        for(ex=[-1, 1])
        color(C_CYAN)
        translate([ex * sr*0.32 + eye_r*0.1, sr*0.06 + eye_r*0.1, 18.5])
            cylinder(r=eye_r * 0.12, h=1);

        color(C_CYAN)
        translate([0, -sr*0.14, 16.5])
        difference() {
            cylinder(r=sr * 0.30, h=1);
            translate([0, sr * 0.25, -1]) cylinder(r=sr * 0.33, h=3);
        }

        for(ex=[-1, 1])
        color("#FF8A80")
        translate([ex * sr*0.55, -sr*0.18, 16.5])
        scale([1, 0.6, 1])
            cylinder(r=sr * 0.08, h=1);
    }
}


// ==================== 头部后壳 ====================

module head_shell() {
    bw_top = BODY_TOP_W;
    bz = 60;
    neck_z = bz + BODY_H;
    sr = SCREEN_D / 2;

    color(C_WHITE)
    translate([0, 0, neck_z])
    hull() {
        scale([1, BODY_D/BODY_W, 1])
            cylinder(r=bw_top/2, h=2);
        translate([0, 0, NECK_H])
        scale([1, 0.75, 1])
            cylinder(r=sr + 15, h=2);
    }

    color(C_WHITE)
    translate([0, 0, neck_z + NECK_H])
    difference() {
        scale([1, 0.72, 0.85])
            sphere(r=sr + 30);
        translate([sr + 5, -sr - 70, -sr - 20])
            cube([sr + 40, (sr + 70)*2, (sr + 70)*2]);
        translate([-sr - 60, -sr - 60, -sr - 60])
            cube([(sr + 60)*2, (sr + 60)*2, sr + 30]);
    }

    color(C_BLUE)
    translate([0, 0, neck_z + NECK_H + HEAD_H - 15])
    scale([1, 0.72, 0.85])
    ring(r=sr + 30, h=4, t=3);
}


// ==================== 天线 ====================

module antenna() {
    bz = 60;
    ant_z = bz + BODY_H + NECK_H + HEAD_H - 10;

    translate([0, -14, ant_z]) {
        color(C_BLUE_DK)
        union() {
            cylinder(h=14, r1=16, r2=9);
            translate([0, 0, 14])
                cylinder(h=6, r1=9, r2=5);
        }
        color(C_BLUE_DK)
        translate([0, 0, 20])
        cylinder(h=70, r1=5, r2=3);
        translate([0, 0, 90])
        color(C_GOLD)
        sphere(r=18);
        translate([-5, 5, 96])
        color("#FFF5A0")
        sphere(r=5);
    }
}


// ==================== 麦克风阵列 ====================

module mic_array() {
    bw_bot = BODY_W;
    bz = 60;
    sr = SCREEN_D / 2;
    mx = bw_bot/2 - 4;
    mz = bz + BODY_H*0.38 - sr - 32;

    translate([mx, 0, mz])
    rotate([0, -90, 0]) {
        color("#1A1C20")
        hull() {
            translate([-35, -8, 0]) cylinder(r=4, h=6);
            translate([ 35, -8, 0]) cylinder(r=4, h=6);
            translate([-35,  8, 0]) cylinder(r=4, h=6);
            translate([ 35,  8, 0]) cylinder(r=4, h=6);
        }
        for(i=[0:3]) {
            translate([-22 + i*15, 0, 6])
            color("#333")
            cylinder(r=2.5, h=2);
            translate([-22 + i*15, 0, 8])
            color("#222")
            cylinder(r=2, h=0.5);
        }
        color("#00FF88")
        translate([-30, -6, 8.5])
            cylinder(r=1.5, h=1);
    }
}


// ==================== 喇叭格栅 + 固定座 ====================

module speaker_grille() {
    // 放在底盘前面板，黑色音箱藏黑色底盘里，完全隐形
    cw = TRACK_W + 90;
    cl = TRACK_L + 50;
    ch = 55;
    // 底盘前面板中心
    sx = 0;
    sy = -(cl/2 - 4);
    sz = ch/2;
    gw = 105;        // 格栅宽
    gh = 25;         // 格栅高（紧凑长条）
    bar_h = 2;       // 横条高
    bar_gap = 2.5;   // 横条间距
    bar_count = 7;

    translate([sx, sy, sz])
    rotate([90, 0, 0]) {
        difference() {
            // 凹陷面板
            color("#2a2c30")
            translate([0, 0, -0.5])
            cube([gw + 8, gh + 6, 1.2], center=true);

            // 横条音孔
            for (i = [0: bar_count - 1]) {
                zz = (i - (bar_count - 1)/2) * (bar_h + bar_gap);
                color(C_DK_GRAY)
                translate([0, zz, -3])
                cube([gw - 4, bar_h, 6], center=true);
            }
        }
    }
}

module speaker_mount() {
    cw = TRACK_W + 90;
    cl = TRACK_L + 50;
    ch = 55;
    // 贴在底盘前面板内侧
    sx = 0;
    sy = -(cl/2 - 18);
    sz = ch/2;
    sp_w = 112;
    sp_h = 34;
    sp_d = 28;    // 音箱厚度21mm + 余量

    translate([sx, sy, sz])
    rotate([90, 0, 0])
    color("#303338") {
        difference() {
            union() {
                // 背板
                cube([sp_w, sp_h, 2], center=true);
                // 上下左右挡边
                translate([0, sp_h/2 - 2, -sp_d/2 + 1])
                cube([sp_w, 3, sp_d], center=true);
                translate([0, -sp_h/2 + 2, -sp_d/2 + 1])
                cube([sp_w, 3, sp_d], center=true);
                translate([sp_w/2 - 2, 0, -sp_d/2 + 1])
                cube([3, sp_h, sp_d], center=true);
                translate([-sp_w/2 + 2, 0, -sp_d/2 + 1])
                cube([3, sp_h, sp_d], center=true);
            }
            // 正面开口
            translate([0, 0, sp_d/2 + 1])
            cube([sp_w - 12, sp_h - 12, sp_d + 2], center=true);
        }
    }
}
}

// ==================== 传感器阵列 ====================

module sensor_array() {
    bw_bot = BODY_W;
    bz = 60;

    for(angle=[-48, -132]) {
        rad = angle * 3.14159 / 180;
        sx = bw_bot/2 * cos(rad);
        sy = bw_bot/2 * sin(rad) * BODY_D/BODY_W;
        sz = bz + BODY_H * 0.22;

        color(C_SENSOR)
        translate([sx, sy, sz])
        rotate([0, -angle + 90, 0])
        union() {
            cylinder(h=10, r1=7, r2=5);
            translate([0, 0, 10]) cylinder(h=4, r=7);
            color("#FF3333")
            translate([0, 0, 14]) cylinder(r=3, h=2);
        }
    }

    // 正面 ToF
    color(C_SENSOR)
    translate([bw_bot/2 + 14, 0, bz + BODY_H * 0.20])
    rotate([0, 90, 0])
    union() {
        cylinder(h=10, r1=7, r2=5);
        translate([0, 0, 10]) cylinder(h=4, r=7);
        color("#00CCFF")
        translate([0, 0, 14]) cylinder(r=3, h=2);
    }
}


// ==================== 机械臂安装座 ====================

module arm_mount_plate(side) {
    bw_bot = BODY_W;
    bz = 60;
    mx = 8;
    my = side * (bw_bot/2 - 10);
    mz = bz + BODY_H * 0.55;
    plate_r = 28;

    color(C_GRAY)
    translate([mx, my, mz])
    rotate([0, 90, 0])
    difference() {
        cylinder(r=plate_r, h=8);
        for(dx=[-1, 1]) for(dy=[-1, 1])
            translate([dx*15.5, dy*15.5, -1])
                cylinder(r=2, h=12);
        cylinder(r=6, h=12);
    }
}


// ==================== 机械臂 ====================

module robot_arm(side) {
    bw_bot = BODY_W;
    bz = 60;
    mx = 8;
    my = side * (bw_bot/2 - 10);
    mz = bz + BODY_H * 0.55;

    translate([mx, my, mz])
    rotate([0, 90, 0])
    rotate([0, 0, side * 25]) {
        color(C_GRAY)
        cylinder(r=24, h=16);

        translate([0, 0, 16])
        rotate([-20, 0, 0])
        color(C_GRAY) {
            cylinder(h=70, r1=15, r2=12);
            translate([0, 0, 70]) sphere(r=18);
            translate([0, 14, 70])
            color("#2a2c30")
            cube([28, 14, 26], center=true);
        }

        translate([0, 0, 16])
        rotate([-20, 0, 0])
        translate([0, 0, 70])
        rotate([30, 0, 0])
        color("#4a4c52") {
            cylinder(h=55, r1=12, r2=9);
            translate([0, 0, 55]) sphere(r=14);
        }

        translate([0, 0, 16])
        rotate([-20, 0, 0])
        translate([0, 0, 70])
        rotate([30, 0, 0])
        translate([0, 0, 55])
        color(C_RED) {
            sphere(r=16);
            for(a=[-1, 0, 1])
            rotate([a * 15, 0, a * 10])
            translate([0, 10, 0])
                cylinder(h=26, r1=5, r2=1.5);
        }
    }
}


// ==================== 完整组装 v5 ====================

module coco_v5() {
    track_chassis();
    body_main();
    bow_tie();
    screen_bezel();
    screen_display();
    head_shell();
    antenna();
    sensor_array();
    mic_array();
    speaker_grille();
    speaker_mount();

    arm_mount_plate(1);
    arm_mount_plate(-1);

    if (SHOW_ARMS) {
        robot_arm(1);
        robot_arm(-1);
    }
}

total_h = 60 + BODY_H + NECK_H + HEAD_H + 98;
cw = TRACK_W + 90;

echo("╔═══════════════════════════╗");
echo("║    Coco v5 — 立式导购机   ║");
echo("╠═══════════════════════════╣");
echo(str("║ 总高: ~", total_h, " mm"));
echo(str("║ 底盘: ", cw, "×", TRACK_L+50, " mm"));
echo(str("║ 机身: ", BODY_W, "mm宽×", BODY_H, "mm高"));
echo(str("║ 屏幕: ", SCREEN_D, "mm (复用)"));
echo(str("║ 打印: 分3段, 各≤220mm"));
echo("╚═══════════════════════════╝");

coco_v5();
