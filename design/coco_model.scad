// ============================================================
// Coco 导购机器人 — 3D 外观 v6.2 (双轴云台: 转头+抬头)
// 屏幕在头部, pan ±50° + tilt 5~55°
// 双 SG90 舵机: pan 左右追踪, tilt 根据人身高自动调节
// 按 F5 预览，F6 渲染导出 STL
// ============================================================
$fn = 120;

// ===== Toggle =====
SHOW_ARMS     = true;
SHOW_EXPLODED = false;

// ===== 核心尺寸（mm）v6.2 =====
SCREEN_D    = 200;    // 圆屏直径
BODY_W      = 280;    // 机身底部宽度
BODY_TOP_W  = 220;    // 机身顶部宽度
BODY_H      = 700;    // 机身高度 (v6.1:600 → v6.2:700, 屏幕再升高100mm)
BODY_D      = 220;    // 机身深度

TRACK_W     = 250;    // 履带中心距
TRACK_L     = 290;    // 履带接地长度
WHEEL_R     = 35;     // 驱动轮半径

SCREEN_TILT_BASE = 28;   // 屏幕基础仰角(°) — 机身正面倾斜角
TILT_ANGLE   = 25;       // 抬头角度(°) 5~55, 预览可调
TILT_MIN     = 5;        // 最低 — 待机低头
TILT_NEUTRAL = 28;       // 中位 — 正常互动
TILT_MAX     = 55;       // 最高 — 向上看高个子
PAN_ANGLE    = 0;        // 转头角度(°) -50~+50

// 3D打印分段
PRINT_SEG1_H = 230;      // 下段 (v6.2: 机身加高, 分段微调)
PRINT_SEG2_H = 235;      // 中段
// 上段 = 700-230-235 = 235mm

// 双 SG90 舵机
SERVO_W = 12.5; SERVO_L = 23.0; SERVO_H = 29.0;
SERVO_SHAFT_D = 4.8; SERVO_MOUNT_D = 28;

// 旋转平台
ROTATE_PLATFORM_D = 230; ROTATE_PLATFORM_H = 5;
BEARING_RING_D = 80; BEARING_RING_H = 4; SHAFT_HOLE_D = 10;

// 俯仰铰链
PIVOT_R = 6;             // 铰链轴半径
PIVOT_Y = 60;            // 铰链在旋转平台后方的距离

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
C_SERVO_PAN  = "#4488CC";
C_SERVO_TILT = "#CC6644";


// ==================== 辅助 ====================

module ring(r, h, t) {
    difference() { cylinder(r=r,h=h,center=true); cylinder(r=r-t,h=h+2,center=true); }
}


// ==================== 履带底盘 ====================

module track_tread(side) {
    sx = side*TRACK_W/2; tw=28; l=TRACK_L+WHEEL_R*2+10;
    translate([sx,0,WHEEL_R+14]) rotate([0,90,0]) color(C_TRACK) {
        difference() {
            hull() { translate([0,l/2,0]) cylinder(r=WHEEL_R+6,h=tw); translate([0,-l/2,0]) cylinder(r=WHEEL_R+6,h=tw); }
            hull() { translate([0,l/2,0]) cylinder(r=WHEEL_R-2,h=tw+4); translate([0,-l/2,0]) cylinder(r=WHEEL_R-2,h=tw+4); }
        }
        for(i=[0:18]) translate([0,-l/2+i*l/18,0]) rotate([90,0,90]) cube([tw+1,3,3],center=true);
    }
}

module drive_wheel(side, fb) {
    translate([side*TRACK_W/2, fb*TRACK_L/2, WHEEL_R+14]) rotate([0,90,0]) {
        color("#1a1a1a") difference() { cylinder(r=WHEEL_R+3,h=12,center=true); cylinder(r=WHEEL_R-3,h=14,center=true); }
        color(C_DK_GRAY) difference() { cylinder(r=WHEEL_R-3,h=10,center=true); for(i=[0:5]) rotate([0,0,i*60]) translate([WHEEL_R*0.5,0,0]) cylinder(r=WHEEL_R*0.18,h=12,center=true); }
        color(C_SILVER) cylinder(r=6,h=8,center=true);
    }
}

module track_chassis() {
    cw=TRACK_W+90; cl=TRACK_L+50; ch=55;
    color(C_DK_GRAY) translate([0,0,4]) hull() for(x=[-1,1],y=[-1,1]) translate([x*(cw/2-16),y*(cl/2-16),0]) cylinder(r=16,h=ch);
    color("#303338") translate([0,0,ch+3]) hull() for(x=[-1,1],y=[-1,1]) translate([x*(cw/2-28),y*(cl/2-28),0]) cylinder(r=8,h=4);
    for(side=[-1,1]) {
        track_tread(side); drive_wheel(side,1); drive_wheel(side,-1);
        color(C_GRAY) translate([side*TRACK_W/2,0,WHEEL_R+14]) rotate([0,90,0])
        hull() { translate([0,TRACK_L/2+WHEEL_R*0.3,0]) cylinder(r=WHEEL_R+7,h=18); translate([0,-TRACK_L/2-WHEEL_R*0.3,0]) cylinder(r=WHEEL_R+7,h=18); }
    }
    for(fb=[-1,1]) color("#2a2c30") translate([0,fb*(cl/2-8),ch/2]) rotate([90,0,0]) hull() { translate([-cw/2+20,0,0]) cylinder(r=6,h=10,center=true); translate([cw/2-20,0,0]) cylinder(r=6,h=10,center=true); }
}


// ==================== 机身主体 ====================

module body_main() {
    bw_bot=BODY_W; bw_top=BODY_TOP_W; bz=60;
    color(C_WHITE) translate([0,0,bz])
    difference() {
        hull() {
            translate([0,0,0])          scale([1,BODY_D/BODY_W,1]) cylinder(r=bw_bot/2,h=8);
            translate([0,0,BODY_H*0.30]) scale([1,BODY_D/BODY_W,1]) cylinder(r=bw_bot/2+8,h=8);
            translate([0,0,BODY_H*0.65]) scale([1,BODY_D/BODY_W,1]) cylinder(r=(bw_bot+bw_top)/4+5,h=8);
            translate([0,0,BODY_H-10])   scale([1,BODY_D/BODY_W,1]) cylinder(r=bw_top/2,h=10);
        }
        translate([bw_bot/2-15,-BODY_D,-5]) cube([40,BODY_D*2,BODY_H+30]);
    }
    color("#F0F2F5") translate([bw_bot/2-17,0,bz+50]) rotate([0,-90,0]) translate([0,0,-1]) cylinder(r=120,h=2);

    // 装饰环
    color(C_BLUE) translate([0,0,bz+BODY_H-22]) scale([1,BODY_D/BODY_W,1]) ring(r=bw_bot/2+5,h=10,t=4);
    color(C_BLUE) translate([0,0,bz+8])         scale([1,BODY_D/BODY_W,1]) ring(r=bw_bot/2+5,h=10,t=4);
    color(C_BLUE) translate([0,0,bz+PRINT_SEG1_H]) scale([1,BODY_D/BODY_W,1]) ring(r=(bw_bot+bw_top)/4+15,h=5,t=2.5);
    color(C_BLUE) translate([0,0,bz+PRINT_SEG1_H+PRINT_SEG2_H]) scale([1,BODY_D/BODY_W,1]) ring(r=(bw_bot+bw_top)/4+8,h=5,t=2.5);

    // === 顶部旋转平台基座 (pan 舵机 + 轴承) ===
    color(C_GRAY) translate([0,0,bz+BODY_H-2]) scale([1,BODY_D/BODY_W,1])
    difference() {
        cylinder(r=bw_top/2-2, h=6);
        translate([0,0,-1]) cylinder(r=12, h=8);
        translate([bw_top/4,0,-1]) cube([SERVO_L+4,SERVO_W+2,8]);
    }
}


// ==================== Pan 舵机安装座 ====================

module pan_servo_mount() {
    bz=60; sz=bz+BODY_H-36;
    color(C_SERVO_PAN) {
        translate([BODY_TOP_W/4,-SERVO_W/2,sz]) cube([SERVO_L,SERVO_W,SERVO_H-6]);
        translate([BODY_TOP_W/4,-SERVO_W/2,sz+SERVO_H-6]) cube([SERVO_L,SERVO_W+16,1.5]);
        translate([BODY_TOP_W/4+SERVO_L/2,0,sz+SERVO_H]) cylinder(r=SERVO_SHAFT_D/2,h=10);
        color("#DDDDDD") translate([BODY_TOP_W/4+SERVO_L/2,0,sz+SERVO_H+10]) cylinder(r=9,h=3);
    }
    color(C_WHITE) for(dx=[-SERVO_MOUNT_D/2,SERVO_MOUNT_D/2])
        translate([BODY_TOP_W/4+SERVO_L/2+dx,0,sz-14]) cylinder(r=4,h=14+SERVO_H+10);
}


// ==================== 双轴头部组件 ====================

module pan_tilt_head() {
    bz=60; neck_z=bz+BODY_H; sr=SCREEN_D/2;
    explode = SHOW_EXPLODED ? 80 : 0;

    translate([0,0,explode])
    rotate([0,0,PAN_ANGLE]) {

        // ===== 1. Pan 旋转平台 =====
        translate([0,0,neck_z+0.5])
        difference() {
            union() {
                color(C_GRAY) scale([1,BODY_D/BODY_W,1]) cylinder(r=BODY_TOP_W/2+4,h=ROTATE_PLATFORM_H);
                color("#50555A") translate([0,0,-3]) cylinder(r=BEARING_RING_D/2+2,h=3);
            }
            translate([0,0,-4]) cylinder(r=SHAFT_HOLE_D,h=ROTATE_PLATFORM_H+8);
        }

        // ===== 2. 俯仰铰链座 (固定在旋转平台上) =====
        pivot_z = neck_z + ROTATE_PLATFORM_H + 8;
        color(C_GRAY)
        for(sy=[-1,1])
        translate([-BODY_TOP_W/4, sy*(BEARING_RING_D/2+6), neck_z+ROTATE_PLATFORM_H])
        difference() {
            hull() {
                translate([0,sy*(-6),0]) cylinder(r=10,h=20);
                translate([PIVOT_Y*0.3,sy*(-6),0]) cylinder(r=8,h=20);
            }
            // 铰链轴孔
            translate([0,0,pivot_z-neck_z-ROTATE_PLATFORM_H]) rotate([0,90,0]) cylinder(r=PIVOT_R,h=40,center=true);
        }

        // ===== 3. Tilt 舵机 (装在旋转平台上方) =====
        tilt_servo_z = neck_z + ROTATE_PLATFORM_H + 2;
        color(C_SERVO_TILT)
        translate([10,-SERVO_W/2,tilt_servo_z]) {
            cube([SERVO_L,SERVO_W,SERVO_H-6]);
            translate([0,-SERVO_W/2,SERVO_H-6]) cube([SERVO_L,SERVO_W+16,1.5]);
            translate([SERVO_L/2,SERVO_W/2,SERVO_H]) cylinder(r=SERVO_SHAFT_D/2,h=8);
            color("#DDDDDD") translate([SERVO_L/2,SERVO_W/2,SERVO_H+8]) cylinder(r=9,h=2.5);
            // 连杆连接到屏幕框
            color("#50555A")
            translate([SERVO_L/2,SERVO_W/2,SERVO_H+10.5])
            rotate([0,20,0])
            cylinder(r=2.5,h=45);
        }

        // ===== 4. 倾斜头部 (绕 pivot 旋转) =====
        translate([0,0,pivot_z])
        rotate([-TILT_ANGLE + SCREEN_TILT_BASE, 0, 0])  // 绕铰链轴俯仰
        translate([0,0,-pivot_z]) {

            // ---- 屏幕外框 ----
            screen_z = pivot_z + 35;
            translate([BODY_TOP_W/2-12, 0, screen_z])
            rotate([SCREEN_TILT_BASE, 0, 0]) {
                // 外框
                color(C_SILVER)
                difference() {
                    cylinder(r=sr+18,h=10);
                    translate([0,0,-1]) cylinder(r=sr+6,h=12);
                }
                color("#B8BCC4") translate([0,0,10])
                difference() { cylinder(r=sr+6,h=3); translate([0,0,-1]) cylinder(r=sr-2,h=5); }
                color("#1A1C20") translate([0,0,13]) ring(r=sr+1,h=2,t=3);
                for(a=[45,135,225,315]) rotate([0,0,a]) translate([sr+14,0,-2])
                color("#A0A4AC")
                difference() { hull() { cylinder(r=8,h=6); translate([-12,0,0]) cylinder(r=6,h=6); } translate([0,0,-1]) cylinder(r=1.7,h=10); }
            }

            // ---- 屏幕显示 ----
            translate([BODY_TOP_W/2-12, 0, screen_z])
            rotate([SCREEN_TILT_BASE, 0, 0]) {
                color(C_SCREEN) translate([0,0,15]) cylinder(r=sr,h=1.5);
                eye_r=sr*0.25;
                for(ex=[-1,1]) {
                    color(C_CYAN) translate([ex*sr*0.32,sr*0.08,16.5]) scale([1,1.25,1]) cylinder(r=eye_r,h=1);
                    color("#0A0C12") translate([ex*sr*0.32,sr*0.06,17.5]) cylinder(r=eye_r*0.35,h=1);
                    color(C_CYAN) translate([ex*sr*0.32+eye_r*0.1,sr*0.06+eye_r*0.1,18.5]) cylinder(r=eye_r*0.12,h=1);
                }
                color(C_CYAN) translate([0,-sr*0.14,16.5]) difference() { cylinder(r=sr*0.30,h=1); translate([0,sr*0.25,-1]) cylinder(r=sr*0.33,h=3); }
                for(ex=[-1,1]) color("#FF8A80") translate([ex*sr*0.55,-sr*0.18,16.5]) scale([1,0.6,1]) cylinder(r=sr*0.08,h=1);
            }

            // ---- 头部后壳 ----
            head_z = screen_z + sr*0.35;
            color(C_WHITE) translate([0,0,head_z])
            difference() {
                scale([1,0.75,1]) rotate([-8,0,0]) scale([1,0.72,0.85]) sphere(r=sr+40);
                translate([sr+30,-sr-80,-sr-30]) cube([sr+50,(sr+80)*2,(sr+60)*2]);
                translate([-sr-80,-sr-80,-sr-80]) cube([(sr+80)*2,(sr+80)*2,sr+40]);
            }
            color(C_BLUE) translate([0,0,head_z+sr*0.5]) scale([1,0.72,0.85]) ring(r=sr+40,h=4,t=3);

            // ---- 天线 ----
            ant_z = head_z + sr*1.05;
            translate([0,-10,ant_z]) {
                color(C_BLUE_DK) { cylinder(h=12,r1=14,r2=8); translate([0,0,12]) cylinder(h=5,r1=8,r2=4); }
                color(C_BLUE_DK) translate([0,0,17]) cylinder(h=60,r1=4,r2=2.5);
                translate([0,0,77]) color(C_GOLD) sphere(r=16);
                translate([-4,4,84]) color("#FFF5A0") sphere(r=4);
            }
        }
    }
}


// ==================== 蝴蝶结 ====================

module bow_tie() {
    bw_bot=BODY_W; bz=60;
    translate([bw_bot/2-30,0,bz+BODY_H*0.52])
    color(C_BLUE_DK) {
        translate([-22,0,0]) rotate([0,15,0]) scale([1,1.5,0.6]) sphere(r=18);
        translate([22,0,0]) rotate([0,-15,0]) scale([1,1.5,0.6]) sphere(r=18);
        sphere(r=12);
        translate([0,0,-8]) rotate([10,0,0]) {
            translate([-6,2,-12]) rotate([0,30,0]) scale([0.4,0.8,0.3]) sphere(r=18);
            translate([6,2,-12]) rotate([0,-30,0]) scale([0.4,0.8,0.3]) sphere(r=18);
        }
    }
}


// ==================== 麦克风阵列 (胸口) ====================

module mic_array() {
    bw_bot=BODY_W; bz=60;
    translate([bw_bot/2-4,0,bz+BODY_H*0.30])
    rotate([0,-90,0]) {
        color("#1A1C20") hull() { for(i=[-1,1],j=[-1,1]) translate([i*35,j*8,0]) cylinder(r=4,h=6); }
        for(i=[0:3]) { translate([-22+i*15,0,6]) color("#333") cylinder(r=2.5,h=2); translate([-22+i*15,0,8]) color("#222") cylinder(r=2,h=0.5); }
        color("#00FF88") translate([-30,-6,8.5]) cylinder(r=1.5,h=1);
    }
}


// ==================== 喇叭 ====================

module speaker_grille() {
    cw=TRACK_W+90; cl=TRACK_L+50; ch=55; gw=105; gh=25; bh=2; bg=2.5; bc=7;
    translate([0,-(cl/2-4),ch/2]) rotate([90,0,0])
    difference() {
        color("#2a2c30") translate([0,0,-0.5]) cube([gw+8,gh+6,1.2],center=true);
        for(i=[0:bc-1]) { zz=(i-(bc-1)/2)*(bh+bg); color(C_DK_GRAY) translate([0,zz,-3]) cube([gw-4,bh,6],center=true); }
    }
}

module speaker_mount() {
    cw=TRACK_W+90; cl=TRACK_L+50; ch=55; spw=112; sph=34; spd=28;
    translate([0,-(cl/2-18),ch/2]) rotate([90,0,0])
    color("#303338") {
        difference() {
            union() {
                cube([spw,sph,2],center=true);
                translate([0,sph/2-2,-spd/2+1]) cube([spw,3,spd],center=true);
                translate([0,-sph/2+2,-spd/2+1]) cube([spw,3,spd],center=true);
                translate([spw/2-2,0,-spd/2+1]) cube([3,sph,spd],center=true);
                translate([-spw/2+2,0,-spd/2+1]) cube([3,sph,spd],center=true);
            }
            translate([0,0,spd/2+1]) cube([spw-12,sph-12,spd+2],center=true);
        }
    }
}


// ==================== 传感器 ====================

module sensor_array() {
    bw_bot=BODY_W; bz=60;
    for(angle=[-48,-132]) {
        rad=angle*3.14159/180;
        color(C_SENSOR) translate([bw_bot/2*cos(rad),bw_bot/2*sin(rad)*BODY_D/BODY_W,bz+BODY_H*0.22])
        rotate([0,-angle+90,0]) union() {
            cylinder(h=10,r1=7,r2=5); translate([0,0,10]) cylinder(h=4,r=7);
            color("#FF3333") translate([0,0,14]) cylinder(r=3,h=2);
        }
    }
    color(C_SENSOR) translate([bw_bot/2+14,0,bz+BODY_H*0.20]) rotate([0,90,0]) union() {
        cylinder(h=10,r1=7,r2=5); translate([0,0,10]) cylinder(h=4,r=7);
        color("#00CCFF") translate([0,0,14]) cylinder(r=3,h=2);
    }
}


// ==================== 机械臂 ====================

module arm_mount_plate(side) {
    translate([8,side*(BODY_W/2-10),60+BODY_H*0.55]) rotate([0,90,0])
    color(C_GRAY) difference() { cylinder(r=28,h=8); for(dx=[-1,1],dy=[-1,1]) translate([dx*15.5,dy*15.5,-1]) cylinder(r=2,h=12); cylinder(r=6,h=12); }
}

module robot_arm(side) {
    translate([8,side*(BODY_W/2-10),60+BODY_H*0.55])
    rotate([0,90,0]) rotate([0,0,side*25]) {
        color(C_GRAY) cylinder(r=24,h=16);
        translate([0,0,16]) rotate([-20,0,0]) color(C_GRAY) { cylinder(h=70,r1=15,r2=12); translate([0,0,70]) sphere(r=18); translate([0,14,70]) color("#2a2c30") cube([28,14,26],center=true); }
        translate([0,0,16]) rotate([-20,0,0]) translate([0,0,70]) rotate([30,0,0]) color("#4a4c52") { cylinder(h=55,r1=12,r2=9); translate([0,0,55]) sphere(r=14); }
        translate([0,0,16]) rotate([-20,0,0]) translate([0,0,70]) rotate([30,0,0]) translate([0,0,55])
        color(C_RED) { sphere(r=16); for(a=[-1,0,1]) rotate([a*15,0,a*10]) translate([0,10,0]) cylinder(h=26,r1=5,r2=1.5); }
    }
}


// ==================== 完整组装 v6.2 ====================

module coco_v6_2() {
    track_chassis();
    body_main();
    pan_servo_mount();
    bow_tie();
    sensor_array();
    mic_array();
    speaker_grille();
    speaker_mount();
    arm_mount_plate(1); arm_mount_plate(-1);
    if (SHOW_ARMS) { robot_arm(1); robot_arm(-1); }
    pan_tilt_head();
}


total_h = 60 + BODY_H + ROTATE_PLATFORM_H + 300;

echo("╔═══════════════════════════════════╗");
echo("║ Coco v6.2 — 双轴云台 转头+抬头   ║");
echo("╠═══════════════════════════════════╣");
echo(str("║ 总高: ~", total_h, " mm"));
echo(str("║ 机身: ", BODY_H, "mm (3段打印)"));
echo(str("║ 屏幕中心: ~", 60+BODY_H+80, " mm"));
echo(str("║ Pan: ±50° / Tilt: ", TILT_MIN, "~", TILT_MAX, "°"));
echo(str("║ 双 SG90 舵机: pan + tilt"));
echo(str("║ 底盘: ", TRACK_W+90, "×", TRACK_L+50, " mm"));
echo("╚═══════════════════════════════════╝");

coco_v6_2();
