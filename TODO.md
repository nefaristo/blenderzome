# TODO List

## Zome Class

- [ ] Make the `derived_geometry` method independent of the rototranslation.
  - **Note**: For now, the rototranslation will be handled at the end, including the derived geometry.
- [ ] draw face barycenter set
- [ ] Add bases and tops to the zome
- [ ] Add a vertical cut of the zome with derived_geometry making triangles for the next radial vertices being missing
- [ ] Complete area calculation of intersecting plane
- [ ] draw_beams either slower version strictly following self.faces or faster rotating the duplicate by (original face normal - actual face normal) 
- [ ] possibly storing face types in the blender object custom property (that would require the immediate creation of the zome object , now faces are just lists of vertices)
