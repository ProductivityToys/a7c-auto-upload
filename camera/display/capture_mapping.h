/* A frame may occupy a subrange of a coalesced stream mapping. Both the CPU
 * interval and its backing offset must match; never accept an unrelated VMA.
 * Inputs are 32-bit camera addresses/offsets, independent of host word size.
 */
static int capture_mapping_matches(unsigned lo,unsigned hi,unsigned mapping_offset,
                                   unsigned pixels_address,unsigned pixels_bytes,
                                   unsigned bitmap_offset){
 if(!pixels_bytes||hi<=lo||pixels_address<lo||pixels_address>=hi||
    pixels_bytes>hi-pixels_address)return 0;
 unsigned delta=pixels_address-lo;
 if(mapping_offset>0xffffffffU-delta)return 0;
 return mapping_offset+delta==bitmap_offset;
}

/* Read-only experiment pinned to the observed 2.00 shooting OSD. Native
 * mapper 0x76f92c selects /dev/mem for 0xfe000000..0xfeffffff; this gate is
 * intentionally narrower. It is never enabled by a display command. */
static int capture_shooting_mapping_matches(unsigned lo,unsigned hi,unsigned mapping_offset,
                                            unsigned pixels_address,unsigned pixels_bytes,
                                            unsigned bitmap_offset){
 return pixels_bytes==614400U && mapping_offset==0xfe33a000U &&
        bitmap_offset==mapping_offset && lo==pixels_address && hi>lo &&
        hi-lo==pixels_bytes &&
        capture_mapping_matches(lo,hi,mapping_offset,pixels_address,pixels_bytes,bitmap_offset);
}
