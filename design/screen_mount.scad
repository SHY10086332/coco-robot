// ============================================================
// Coco v6.2 — 双轴云台完整头部组件 (一体旋转)
// 屏幕+外壳+天线 整个头部绕铰链俯仰，不再只有屏幕动
// SG90 ×2: pan ±50°水平旋转 + tilt 5°~55°俯仰
// 用法: 打开此文件 → F6渲染 → Export as STL
// ============================================================
$fn = 120;

SCREEN_D     = 200;
SCREEN_TILT  = 28;       // 屏幕基础仰角(头部前面板的倾斜)
ROTATE_PLATFORM_D = 220;
ROTATE_PLATFORM_H = 5;
BEARING_RING_D = 80;
SHAFT_HOLE_D = 10;

// 俯仰参数
TILT_ANGLE = 28;          // 当前仰角 (5~55), 可调预览
TILT_MIN = 5;
TILT_MAX = 55;

// 铰链位置 — 在旋转平台后部
PIVOT_X = -35;            // 铰链在平台中心后方
PIVOT_Z = 22;             // 铰链在平台上方高度
PIVOT_R = 3;              // 铰链轴半径

// SG90 舵机尺寸
SERVO_W = 12.5; SERVO_L = 23.0; SERVO_H = 29.0;

// ===== 颜色 =====
C_WHITE    = "#F7F8FA";
C_BLUE     = "#4A90D9";
C_BLUE_DK  = "#2C5F8A";
C_CYAN     = "#00FFD0";
C_SCREEN   = "#0A0C12";
C_GRAY     = "#3A3C42";
C_SILVER   = "#D0D4DC";
C_GOLD     = "#FFD700";
C_SERVO_PAN  = "#4488CC";
C_SERVO_TILT = "#CC6644";


// ================================================================
// 1. 旋转底盘 (pan轴 — 固定在机身上)
// ================================================================
module rotation_base() {
    difference() {
        union() {
            color("#D0D4DC") cylinder(r=ROTATE_PLATFORM_D/2, h=ROTATE_PLATFORM_H);
            color("#50555A") translate([0,0,-3]) cylinder(r=BEARING_RING_D/2+2, h=3);
        }
        translate([0,0,-5]) cylinder(r=SHAFT_HOLE_D, h=ROTATE_PLATFORM_H+12);
        translate([0,0,-0.5]) cylinder(r=10, h=3);  // 舵盘槽
    }
}

// ================================================================
// 2. Pan舵机安装座 (固定在旋转底盘下方，插入机身)
// ================================================================
module pan_servo_mount() {
    color(C_SERVO_PAN)
    translate([BEARING_RING_D/2-5, -SERVO_W/2, ROTATE_PLATFORM_H-25])
    difference() {
        union() {
            cube([SERVO_L, SERVO_W, SERVO_H-6]);
            translate([0, 0, SERVO_H-6]) cube([SERVO_L, SERVO_W+16, 1.5]);
        }
        // 安装耳
        for(dx=[-SERVO_L*0.35, SERVO_L*0.35])
            translate([SERVO_L/2+dx, SERVO_W/2, SERVO_H+2]) cylinder(r=1.5, h=12);
    }
    // 舵机轴
    color("#CCCCCC")
    translate([BEARING_RING_D/2-5+SERVO_L/2, 0, ROTATE_PLATFORM_H-25+SERVO_H])
    cylinder(r=SERVO_W/4, h=ROTATE_PLATFORM_H+3);
    // 舵盘
    color("#DDDDDD")
    translate([BEARING_RING_D/2-5+SERVO_L/2, 0, ROTATE_PLATFORM_H+0.5])
    cylinder(r=9, h=3);
}

// ================================================================
// 3. 俯仰铰链支架 (在旋转平台上，后方)
// ================================================================
module tilt_hinge_brackets() {
    color("#B0B4BC")
    for(sy=[-BEARING_RING_D/2-5, BEARING_RING_D/2+5])
    translate([PIVOT_X, sy, ROTATE_PLATFORM_H])
    difference() {
        hull() {
            translate([0, 0, 0]) cylinder(r=7, h=PIVOT_Z);
            translate([12, 0, 0]) cylinder(r=6, h=PIVOT_Z);
        }
        // 铰链轴孔
        translate([0, 0, PIVOT_Z]) rotate([0, 90, 0]) cylinder(r=PIVOT_R, h=30, center=true);
    }
}

// ================================================================
// 4. Tilt舵机座 (在旋转平台上，前部)
// ================================================================
module tilt_servo_mount() {
    color(C_SERVO_TILT)
    translate([ROTATE_PLATFORM_D/2-30, -SERVO_W/2, ROTATE_PLATFORM_H+3])
    {
        cube([SERVO_L, SERVO_W, SERVO_H-6]);
        translate([0, -SERVO_W/2, SERVO_H-6]) cube([SERVO_L, SERVO_W+16, 1.5]);
        // 舵机轴
        translate([SERVO_L/2, SERVO_W/2, SERVO_H]) cylinder(r=SERVO_W/4, h=6);
        color("#DDDDDD") translate([SERVO_L/2, SERVO_W/2, SERVO_H+6]) cylinder(r=8, h=2);
    }
}

// ================================================================
// 5. 完整头部 — 屏幕+外壳+天线 (绕铰链俯仰)
// ================================================================
module head_assembly() {
    sr = SCREEN_D/2;

    // 铰链轴位置
    pivot_x = PIVOT_X;
    pivot_z = ROTATE_PLATFORM_H + PIVOT_Z;

    // 头部中心 (屏幕前方)
    head_cx = 65;      // 头部中心X偏移(平台中心→前方)
    head_cz = pivot_z + 70;  // 头部中心高度

    // ---- 屏幕外框 ----
    color(C_SILVER)
    translate([head_cx, 0, head_cz])
    rotate([SCREEN_TILT, 0, 0])
    difference() {
        cylinder(r=sr+18, h=12);
        translate([0,0,1]) cylinder(r=sr+6, h=13);
    }

    // 屏幕嵌入台阶
    color("#B0B4BC")
    translate([head_cx, 0, head_cz])
    rotate([SCREEN_TILT, 0, 0])
    difference() {
        translate([0,0,12]) cylinder(r=sr+6, h=4);
        translate([0,0,10]) cylinder(r=sr-2, h=8);
    }

    // 屏幕黑色面板
    color(C_SCREEN)
    translate([head_cx, 0, head_cz])
    rotate([SCREEN_TILT, 0, 0])
    translate([0,0,15]) cylinder(r=sr, h=1.5);

    // Coco 表情 (简化, 屏幕在正面)
    color(C_CYAN)
    translate([head_cx, 0, head_cz])
    rotate([SCREEN_TILT, 0, 0])
    {
        for(ex=[-1,1])
            translate([ex*sr*0.32, sr*0.08, 16.5])
            scale([1, 1.25, 1]) cylinder(r=sr*0.25, h=1);
        // 微笑
        translate([0, -sr*0.14, 16.5])
        difference() {
            cylinder(r=sr*0.30, h=1);
            translate([0, sr*0.25, -1]) cylinder(r=sr*0.33, h=3);
        }
    }

    // 安装支耳 ×4 (M3)
    for(a=[45,135,225,315])
    rotate([0,0,a])
    translate([head_cx, 0, head_cz])
    rotate([SCREEN_TILT, 0, 0])
    translate([sr+14, 0, 2])
    color("#A0A4AC")
    difference() {
        hull() { cylinder(r=8, h=6); translate([-12,0,0]) cylinder(r=6, h=6); }
        translate([0,0,-1]) cylinder(r=1.7, h=10);
    }

    // ---- 头部后壳 (半球壳, 从屏幕框向后延伸) ----
    shell_cx = head_cx - 10;    // 壳体在屏幕后方
    shell_cz = head_cz + sr*0.2;

    color(C_WHITE)
    translate([shell_cx, 0, shell_cz])
    rotate([SCREEN_TILT, 0, 0])
    difference() {
        scale([1, 0.78, 1])
        rotate([-5, 0, 0])
        scale([1, 0.75, 0.9])
        sphere(r=sr+42);

        // 前面挖空(给屏幕)
        translate([sr+20, -sr-60, -sr-40]) cube([sr+30, (sr+60)*2, (sr+60)*2]);
        // 底部切平
        translate([-sr-80, -sr-80, -sr-60]) cube([(sr+80)*2, (sr+80)*2, sr+30]);
    }

    // 壳体外装饰环
    color(C_BLUE)
    translate([shell_cx, 0, shell_cz+sr*0.55])
    rotate([SCREEN_TILT, 0, 0])
    scale([1, 0.75, 0.9])
    ring(r=sr+42, h=4, t=3);

    // ---- 天线 (从壳顶伸出) ----
    ant_base_x = shell_cx - 8;
    ant_base_z = shell_cz + sr*0.95;

    translate([ant_base_x, -8, ant_base_z])
    rotate([SCREEN_TILT-5, 0, 0])
    {
        color(C_BLUE_DK) {
            cylinder(h=10, r1=12, r2=7);
            translate([0, 0, 10]) cylinder(h=4, r1=7, r2=3);
        }
        color(C_BLUE_DK) translate([0, 0, 14]) cylinder(h=55, r1=3.5, r2=2);
        translate([0, 0, 69]) color(C_GOLD) sphere(r=14);
        translate([-3, 3, 76]) color("#FFF5A0") sphere(r=3.5);
    }

    // ---- 铰链耳 (头壳后方, 连接铰链支架) ----
    color("#B0B4BC")
    for(sy=[-BEARING_RING_D/2-5, BEARING_RING_D/2+5])
    translate([PIVOT_X, sy, pivot_z])
    rotate([0, 90, 0])
    difference() {
        cylinder(r=8, h=14);
        cylinder(r=PIVOT_R+0.3, h=20, center=true);
    }

    // ---- 连杆连接点 (屏幕框后部, 接tilt舵机连杆) ----
    sr_x = ROTATE_PLATFORM_D/2 - 30 + SERVO_L/2;
    sr_z = ROTATE_PLATFORM_H + 3 + SERVO_H + 8;
    color("#888C94")
    translate([sr_x, 0, sr_z])
    rotate([0, 90, 0])
    cylinder(r=3, h=12);
}

// ================================================================
// Tilt 连杆 (从舵机臂到头部连接点)
// ================================================================
module tilt_linkage() {
    servo_x = ROTATE_PLATFORM_D/2 - 30 + SERVO_L/2;
    servo_z = ROTATE_PLATFORM_H + 3 + SERVO_H + 8;

    color("#888C94")
    translate([servo_x, 0, servo_z])
    hull() {
        cylinder(r=2.5, h=4);
        translate([0, 12, 25]) cylinder(r=2.5, h=4);
    }
}

// ===== 辅助: ring =====
module ring(r, h, t) {
    difference() {
        cylinder(r=r, h=h, center=true);
        cylinder(r=r-t, h=h+2, center=true);
    }
}


// ================================================================
// 完整装配
// ================================================================
echo("===== 双轴云台完整头部组件 v6.2 =====");
echo(str("屏幕: Ø", SCREEN_D, "mm, 仰角 ", TILT_MIN, "°~", TILT_MAX, "°"));
echo(str("头部: 屏幕+外壳+天线 一体俯仰"));
echo(str("铰链轴: X=", PIVOT_X, " Z=", ROTATE_PLATFORM_H+PIVOT_Z));
echo(str("舵机: SG90 ×2 (pan + tilt)"));
echo("======================================");

// 固定部分 (相对于机身)
rotation_base();
pan_servo_mount();

// 旋转平台上的固定件
tilt_hinge_brackets();
tilt_servo_mount();

// ═══ 整个头部绕铰链俯仰 ═══
translate([PIVOT_X, 0, ROTATE_PLATFORM_H+PIVOT_Z])
rotate([-TILT_ANGLE + SCREEN_TILT, 0, 0])
translate([-PIVOT_X, 0, -(ROTATE_PLATFORM_H+PIVOT_Z)])
{
    head_assembly();
    tilt_linkage();
}
