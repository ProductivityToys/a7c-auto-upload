#include <assert.h>
#include <stdio.h>
#include "../capture_mapping.h"
int main(void){
 unsigned n=640*480*2;
 assert(capture_mapping_matches(0x10000000,0x10096000,0x200000,0x10000000,n,0x200000));
 assert(capture_mapping_matches(0x10000000,0x10200000,0x200000,0x10096000,n,0x296000));
 assert(!capture_mapping_matches(0x10000000,0x10200000,0x200000,0x10096000,n,0x200000));
 assert(!capture_mapping_matches(0x10000000,0x10100000,0x200000,0x10096000,n,0x296000));
 assert(!capture_mapping_matches(0x10000000,0x10200000,0x200000,0x0fffffff,n,0x1fffff));
 assert(!capture_mapping_matches(0x10000000,0x10200000,0x200000,0x10200000,n,0x400000));
 assert(!capture_mapping_matches(0x10000000,0x10200000,0xffff0000,0x10096000,n,0x86000));
 assert(!capture_mapping_matches(0x10000000,0x10200000,0x200000,0x10000000,0,0x200000));
 assert(!capture_mapping_matches(0xffffff00,0x200,0,0xffffff00,0x300,0));
 assert(!capture_mapping_matches(0x10000000,0x10000000,0,0x10000000,n,0));
 assert(capture_shooting_mapping_matches(0x14cee000,0x14d84000,0xfe33a000,0x14cee000,n,0xfe33a000));
 assert(!capture_shooting_mapping_matches(0x14cee000,0x14d84000,0xfe33b000,0x14cee000,n,0xfe33b000));
 assert(!capture_shooting_mapping_matches(0x14cee000,0x14d84000,0x22ab2000,0x14cee000,n,0x22ab2000));
 assert(!capture_shooting_mapping_matches(0x14cee000,0x14d85000,0xfe33a000,0x14cee000,n,0xfe33a000));
 assert(!capture_shooting_mapping_matches(0x14ced000,0x14d84000,0xfe339000,0x14cee000,n,0xfe33a000));
 assert(!capture_shooting_mapping_matches(0x14cee000,0x14d84000,0xfe33a000,0x14cee000,n-1,0xfe33a000));
 assert(!capture_shooting_mapping_matches(0x14cee000,0x14d84000,0xfe33a000,0x14cee001,n,0xfe33a000));
 puts("PASS: exact and coalesced frames; backing mismatch, overrun, address/offset overflow and empty ranges refused");
}
