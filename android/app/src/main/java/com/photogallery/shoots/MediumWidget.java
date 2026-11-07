package com.photogallery.shoots;

public class MediumWidget extends ShootWidget {
    int layout() { return R.layout.widget_medium; }
    int[] whenIds() { return new int[]{R.id.w1, R.id.w2, R.id.w3}; }
    int[] titleIds() { return new int[]{R.id.t1, R.id.t2, R.id.t3}; }
    int[] subIds() { return new int[]{R.id.s1, R.id.s2, R.id.s3}; }
    int[] rowIds() { return new int[]{R.id.r1, R.id.r2, R.id.r3}; }
}
