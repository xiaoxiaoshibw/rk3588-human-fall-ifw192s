
#include <cmath>
#include <vector>
#include <initializer_list>
namespace torch {
template<class T,int D> struct TensorAccessor {
 T* p;std::vector<int> shape;
 auto operator[](int i) const {int n=1;for(int k=1;k<D;k++)n*=shape[k];
 return TensorAccessor<T,D-1>{p+i*n,std::vector<int>(shape.begin()+1,shape.end())};}
};
template<class T> struct TensorAccessor<T,1> {T* p;std::vector<int> shape;T& operator[](int i)const{return p[i];}};
}
namespace at {
enum {kInt,kCPU};
struct TensorOptions {TensorOptions dtype(int){return *this;}TensorOptions device(int){return *this;}};
struct Tensor {std::vector<int> data,shape;template<class T,int D> torch::TensorAccessor<T,D> accessor(){return {(T*)data.data(),shape};}};
Tensor zeros(std::initializer_list<int> dims,TensorOptions){int n=1;for(int d:dims)n*=d;return {std::vector<int>(n,0),std::vector<int>(dims)};}
}
template <typename T, typename T_int>
void dynamic_voxelize_kernel(const torch::TensorAccessor<T, 2> points,
                             torch::TensorAccessor<T_int, 2> coors,
                             const std::vector<float> voxel_size,
                             const std::vector<float> coors_range,
                             const std::vector<int> grid_size,
                             const int num_points, const int num_features,
                             const int NDim) {
  const int ndim_minus_1 = NDim - 1;
  bool failed = false;
  // int coor[NDim];
  int* coor = new int[NDim]();
  int c;

  for (int i = 0; i < num_points; ++i) {
    failed = false;
    for (int j = 0; j < NDim; ++j) {
      c = floor((points[i][j] - coors_range[j]) / voxel_size[j]);
      // necessary to rm points out of range
      if ((c < 0 || c >= grid_size[j])) {
        failed = true;
        break;
      }
      coor[ndim_minus_1 - j] = c;
    }

    for (int k = 0; k < NDim; ++k) {
      if (failed)
        coors[i][k] = -1;
      else
        coors[i][k] = coor[k];
    }
  }

  delete[] coor;
  return;
}

template <typename T, typename T_int>
void hard_voxelize_kernel(const torch::TensorAccessor<T, 2> points,
                          torch::TensorAccessor<T, 3> voxels,
                          torch::TensorAccessor<T_int, 2> coors,
                          torch::TensorAccessor<T_int, 1> num_points_per_voxel,
                          torch::TensorAccessor<T_int, 3> coor_to_voxelidx,
                          int& voxel_num, const std::vector<float> voxel_size,
                          const std::vector<float> coors_range,
                          const std::vector<int> grid_size,
                          const int max_points, const int max_voxels,
                          const int num_points, const int num_features,
                          const int NDim) {
  // declare a temp coors
  at::Tensor temp_coors = at::zeros(
      {num_points, NDim}, at::TensorOptions().dtype(at::kInt).device(at::kCPU));

  // First use dynamic voxelization to get coors,
  // then check max points/voxels constraints
  dynamic_voxelize_kernel<T, int>(points, temp_coors.accessor<int, 2>(),
                                  voxel_size, coors_range, grid_size,
                                  num_points, num_features, NDim);

  int voxelidx, num;
  auto coor = temp_coors.accessor<int, 2>();

  for (int i = 0; i < num_points; ++i) {
    // T_int* coor = temp_coors.data_ptr<int>() + i * NDim;

    if (coor[i][0] == -1) continue;

    voxelidx = coor_to_voxelidx[coor[i][0]][coor[i][1]][coor[i][2]];

    // record voxel
    if (voxelidx == -1) {
      voxelidx = voxel_num;
      if (max_voxels != -1 && voxel_num >= max_voxels) continue;
      voxel_num += 1;

      coor_to_voxelidx[coor[i][0]][coor[i][1]][coor[i][2]] = voxelidx;

      for (int k = 0; k < NDim; ++k) {
        coors[voxelidx][k] = coor[i][k];
      }
    }

    // put points into voxel
    num = num_points_per_voxel[voxelidx];
    if (max_points == -1 || num < max_points) {
      for (int k = 0; k < num_features; ++k) {
        voxels[voxelidx][num][k] = points[i][k];
      }
      num_points_per_voxel[voxelidx] += 1;
    }
  }

  return;
}


extern "C" __declspec(dllexport) int ref_voxel(float* p,int count,int feat,float* v,int* c,int* n,
 float* sizes,float* bounds,int maxp,int maxv){
 std::vector<float> sz(sizes,sizes+3),ran(bounds,bounds+6);std::vector<int> grid(3);
 for(int j=0;j<3;j++)grid[j]=round((bounds[j+3]-bounds[j])/sizes[j]);
 std::vector<int> lookup(grid[0]*grid[1]*grid[2],-1);int num=0;
 hard_voxelize_kernel<float,int>({p,{count,feat}},{v,{maxv,maxp,feat}},{c,{maxv,3}},{n,{maxv}},
 {lookup.data(),{grid[2],grid[1],grid[0]}},num,sz,ran,grid,maxp,maxv,count,feat,3);
 return num;
}
