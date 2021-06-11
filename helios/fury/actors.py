from helios.fury.tools import Uniform, Uniforms
from fury.shaders import add_shader_callback, attribute_to_actor
from fury.shaders import shader_to_actor, load
import fury.primitive as fp
from fury.utils import get_actor_from_primitive
from fury.utils import (vertices_from_actor, array_from_actor,
    update_actor, compute_bounds)

import numpy as np
from vtk.util import numpy_support



class FurySuperNode:
    def __init__(
        self,
        positions,
        colors=(0, 1, 0),
        scales=1,
        marker='3d',
        edge_width=.0,
        edge_color=(255, 255, 255),
    ):
        self._vcount = positions.shape[0]
        self._composed_by_superactors = False

        # to avoid any kind of expansive calculations when we
        # are dealing with just 2d markers
        self._marker_is_3d = marker == '3d'

        self._marker_is_uniform = isinstance(marker, str)
        self._marker = marker if self._marker_is_uniform else None

        self._edge_width_is_uniform = True 
        self._edge_color_is_uniform = True 
        self._edge_opacity_is_uniform = True 
        self._marker_opacity_is_uniform = True 
        # self._edge_width_is_uniform = isinstance(edge_width, float)
        # self._edge_color_is_uniform = len(edge_color) == 3
        self._positions_is_uniform = False

        self.vtk_actor = self._init_actor(
            positions, colors, scales)

        self.uniforms_list = []

        self._init_marker_property(marker)
        self._init_edge_width_property(edge_width)
        self._init_edge_color_property(edge_color)
        self._init_edge_opacity_property(1)
        self._init_marker_opacity_property(1)

        self.uniforms_list.append(
           Uniform(
                name='edgeOpacity', uniform_type='f', value=1))
        self.uniforms_list.append(
           Uniform(
                name='markerOpacity', uniform_type='f', value=1))

        if len(self.uniforms_list) > 0:
            self.Uniforms = Uniforms(self.uniforms_list)
            self.uniforms_observerId = add_shader_callback(
                    self.vtk_actor, self.Uniforms)

            self._init_shader_frag()

    def update(self):
        """Force actor update
        """
        update_actor(self.vtk_actor)
        compute_bounds(self.vtk_actor)

    def _init_actor(self, centers, colors, scales):
        verts, faces = fp.prim_square()
        res = fp.repeat_primitive(
            verts, faces, centers=centers,
            colors=colors,
            scales=scales)

        big_verts, big_faces, big_colors, big_centers = res
        sq_actor = get_actor_from_primitive(
            big_verts, big_faces, big_colors)
        sq_actor.GetMapper().SetVBOShiftScaleMethod(False)
        sq_actor.GetProperty().BackfaceCullingOff()

        attribute_to_actor(sq_actor, big_centers, 'center')
        return sq_actor

    def _init_marker_property(self, marker):
        marker2id = {
            'o': 0, 's': 1, 'd': 2, '3d':0}

        if self._marker_is_uniform:
            print('creating an uniform')
            marker_value = marker2id[marker]
            self.uniforms_list.append(
                Uniform(
                    name='marker', uniform_type='f', value=marker_value))
        else:
            list_of_markers = [marker2id[i] for i in marker]

            list_of_markers = np.repeat(list_of_markers, 4).astype('float')
            attribute_to_actor(
                self.vtk_actor,
                list_of_markers, 'marker')

    def _init_edge_color_property(self, edge_color):
        # if self._edge_color_is_uniform:
        self.uniforms_list.append(
            Uniform(
                name='edgeColor', uniform_type='3f', value=edge_color))
        # else:
        #     edge_colors = np.repeat(
        #        edge_color, 4).astype('float')
        #     attribute_to_actor(
        #         self.vtk_actor,
        #         edge_colors, 'edgeColor')

    def _init_edge_width_property(self, edge_width):
        self.uniforms_list.append(
            Uniform(
                name='edgeWidth', uniform_type='f', value=edge_width))

    def _init_edge_opacity_property(self, opacity):
        self.uniforms_list.append(
            Uniform(
                name='edgeOpacity', uniform_type='f', value=opacity))

    def _init_marker_opacity_property(self, opacity):
        self.uniforms_list.append(
            Uniform(
                name='markerOpacity', uniform_type='f', value=opacity))

    @property
    def shader_dec_vert(self):
        shader = load("billboard_dec.vert")
        if not self._marker_is_3d and not self._marker_is_uniform:
            shader += """
                    //in float edgeWidth;
                    in float marker;
                    out float vMarker;"""
        return shader

    @property
    def shader_impl_vert(self):
        shader = load("billboard_impl.vert")
        if not self._marker_is_3d and not self._marker_is_uniform:
            shader += """
                vMarker = marker;
                //vMarkerOpacity = markerOpacity;"""

        return shader

    @property
    def shader_dec_frag(self):
        shader = load("billboard_dec.frag")
        if self._marker_opacity_is_uniform:
            shader += "uniform float markerOpacity;"
        if self._edge_opacity_is_uniform:
            shader += "uniform float edgeOpacity;"
        if self._edge_width_is_uniform: 
            shader += "uniform float edgeWidth;"
        if self._edge_color_is_uniform:
            shader += "uniform vec3 edgeColor;"
        if self._marker_is_uniform:
            shader += "uniform float marker;"
        else:
            shader += "in float vMarker;"

        shader += """
            uniform mat4 MCDCMatrix;
            uniform mat4 MCVCMatrix;

            float ndot(vec2 a, vec2 b ) {
                return a.x*b.x - a.y*b.y;
            };
            vec3 getDistFunc0(vec2 p, float s, float edgeWidth){
                //circle or sphere sdf func
                float  sdf = 0;
                float minSdf = 0;

                edgeWidth = edgeWidth/2.;
                minSdf = 0.5;
                sdf = -length(p) + s;

                vec3 result = vec3(sdf, minSdf, edgeWidth);
                return result ;
            };
            vec3 getDistFunc1(vec2 p, float s, float edgeWidth){
                //square sdf func
                float  sdf = 0;
                float minSdf = 0;

                edgeWidth = edgeWidth/2.;
                minSdf = 0.5;
                sdf = -length(p) + s;

                vec3 result = vec3(sdf, minSdf, edgeWidth);
                return result ;
            };
            vec3 getDistFunc2(vec2 p, float s, float edgeWidth){
                //diamond sdf func
                float  sdf = 0;
                float minSdf = 0;

                edgeWidth = edgeWidth/2.;
                minSdf = 0.5/2.0;
                vec2 d = abs(p) - vec2(s, s);
                sdf = -length(max(d,0.0)) - min(max(d.x,d.y),0.0);

                vec3 result = vec3(sdf, minSdf, edgeWidth);
                return result ;
            };
            vec3 getDistFunc(vec2 p, float s, float edgeWidth, float marker){
                if (marker == 0.){
                    return getDistFunc0(p, s, edgeWidth);
                }else if  (marker == 1.){
                    return getDistFunc1(p, s, edgeWidth);
                }
                return getDistFunc2(p, s, edgeWidth);
            }
            """
        return shader

    @property
    def shader_impl_frag(self):
        shader = load("billboard_impl.frag")

        shader += """
        float len = length(point);
        float radius = 1.;
        float s = 0.5;
        """
        if self._marker_is_uniform:
            shader += "vec3 result = getDistFunc(point.xy, s, edgeWidth, marker);"
        else:
            shader += "vec3 result = getDistFunc(point.xy, s, edgeWidth, vMarker);"

        shader += """
            float sdf = result.x;
            float minSdf = result.y;
            float edgeWidthNew = result.z;

            if (sdf<0.0) discard;"""

        if self._marker_is_3d:
            shader += """
            /* Calculating the 3D distance d from the center */
            float d = sqrt(1. - len*len);

            /* Calculating the normal as if we had a sphere of radius len*/
            vec3 normalizedPoint = normalize(vec3(point.xy, d));

            /* Defining a fixed light direction */
            vec3 direction = normalize(vec3(1., 1., 1.));

            /* Calculating diffuse */
            float ddf = max(0, dot(direction, normalizedPoint));

            /* Calculating specular */
            float ssf = pow(ddf, 24);

            /* Obtaining the two clipping planes for depth buffer */
            float far = gl_DepthRange.far;
            float near = gl_DepthRange.near;

            /* Getting camera Z vector */
            vec3 cameraZ = vec3(MCVCMatrix[0][2], MCVCMatrix[1][2], MCVCMatrix[2][2]);

            /* Get the displaced position based on camera z by adding d
            in this direction */
            vec4 positionDisplaced = vec4(centerVertexMCVSOutput.xyz
                                        +cameraZ*d,1.0);

            /* Projecting the displacement to the viewport */
            vec4 positionDisplacedDC = (MCDCMatrix*positionDisplaced);

            /* Applying perspective transformation to z */
            float depth = positionDisplacedDC.z/positionDisplacedDC.w;

            /* Interpolating the z of the displacement between far and near planes */
            depth = ((far-near) * (depth) + near + far) / 2.0;

            /* Writing the final depth to depth buffer */
            gl_FragDepth = depth;

            /* Calculating colors based on a fixed light */
            fragOutput0 = vec4(max(color*0.5+ddf * color, ssf * vec3(1)), 1);
            """
        else:
            shader += """
                vec4 rgba = vec4(  color, markerOpacity );
                if (edgeWidthNew > 0.0){
                if (sdf < edgeWidthNew)  rgba  = vec4(edgeColor, edgeOpacity);
                }

                fragOutput0 = rgba;
            """

        return shader

    def _init_shader_frag(self):
        # fs_impl_code = load('billboard_impl.frag')
        # if self._marker_is_3d:
        #     fs_impl_code += f'{load("billboard_spheres_impl.frag")}'
        # else:
        #     fs_impl_code += f'{load("marker_billboard_impl.frag")}'
        shader_to_actor(
            self.vtk_actor,
            "vertex", impl_code=self.shader_impl_vert,
            decl_code=self.shader_dec_vert)
        shader_to_actor(
            self.vtk_actor,
            "fragment", decl_code=self.shader_dec_frag)
        shader_to_actor(
            self.vtk_actor,
            "fragment", impl_code=self.shader_impl_frag,
            block="light")

    @property
    def edge_width(self):
        if self._edge_width_is_uniform:
            return self.Uniforms.edgeWidth

    @edge_width.setter
    def edge_width(self, data):
        if self._edge_width_is_uniform:
            self.Uniforms.edgeWidth = data

    @property
    def marker(self):
        pass

    @marker.setter
    def marker(self, data):
        pass

    @property
    def edge_color(self):
        pass

    @edge_color.setter
    def edge_color(self, data):
        pass
    
    @property
    def positions(self):
        pass

    @positions.setter
    def positions(self, pos):
        """positions never it's a uniform variable
        """
        # spheres_positions = numpy_support.vtk_to_numpy(
        #     self.vtk_actor.GetMapper().GetInput().GetPoints().GetData())
        # spheres_positions[:] = self.sphere_geometry + \
        #     np.repeat(pos, self.geometry_length, axis=0)

        # self.vtk_actor.GetMapper().GetInput().GetPoints().GetData().Modified()
        # self.vtk_actor.GetMapper().GetInput().ComputeBounds()
        # pass

    def __str__(self):
        return f'FurySuperActorNode num_nodes {self._vcount}'

    def __repr__(self):
        return f'FurySuperActorNode num_nodes {self._vcount}'


class FurySuperActorNetwork:
    def __init__(
        self,
        positions,
        colors=(0, 1, 0),
        scales=1,
        marker='o',
        edge_width=.0,
        edge_color=(255, 255, 255),
    ):
        self._composed_by_superactors = True
        self.nodes = FurySuperNode(
            positions=positions,
            colors=colors,
            scales=scales,
            marker=marker,
            edge_width=edge_width,
            edge_color=edge_color
        )
        # self.edges = FurySuperEdges(positions, ...)

        self.vtk_actors = [self.nodes.vtk_actor, ]

    @property
    def positions(self):
        return self.nodes.positions

    @positions.setter
    def positions(self, data):
        self.nodes.positions = data
        # self.edges.positions = data