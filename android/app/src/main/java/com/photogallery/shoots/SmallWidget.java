package com.photogallery.shoots;

public class SmallWidget extends ShootWidget {
    int layout() { return R.layout.widget_small; }
    int[] whenIds() { return new int[]{R.id.w1}; }
    int[] titleIds() { return new int[]{R.id.t1}; }
    int[] subIds() { return new int[]{R.id.s1}; }
    int[] rowIds() { return new int[]{R.id.r1}; }
}
