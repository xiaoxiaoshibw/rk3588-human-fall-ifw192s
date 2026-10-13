"""Pinned C++ kernel bodies with minimal accessor host shim, not Torch/CUDA package equivalence."""
import ctypes
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from cpu_pointpillars import Voxelization
from experiment import sha

ROOT=Path(__file__).resolve().parent


def main(out):
    out.mkdir(exist_ok=False)
    source=ROOT/'artifacts/det03_upstream_r1/pointpillars/ops/voxelization/voxelization_cpu.cpp'
    s=source.read_text(encoding='utf-8')
    body=s[s.index('template <typename T, typename T_int>'):s.index('}  // namespace')]
    # Kernel algorithm text is preserved verbatim; this shim replaces ATen allocation/accessors only.
    prefix=r'''
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
'''
    wrapper=r'''
extern "C" __declspec(dllexport) int ref_voxel(float* p,int count,int feat,float* v,int* c,int* n,
 float* sizes,float* bounds,int maxp,int maxv){
 std::vector<float> sz(sizes,sizes+3),ran(bounds,bounds+6);std::vector<int> grid(3);
 for(int j=0;j<3;j++)grid[j]=round((bounds[j+3]-bounds[j])/sizes[j]);
 std::vector<int> lookup(grid[0]*grid[1]*grid[2],-1);int num=0;
 hard_voxelize_kernel<float,int>({p,{count,feat}},{v,{maxv,maxp,feat}},{c,{maxv,3}},{n,{maxv}},
 {lookup.data(),{grid[2],grid[1],grid[0]}},num,sz,ran,grid,maxp,maxv,count,feat,3);
 return num;
}
'''
    cpp=out/'voxel_kernel_host.cpp';cpp.write_text(prefix+body+wrapper,encoding='utf-8')
    dll=out/'voxel_kernel_host.dll';cmd=['g++','-O2','-shared','-static',str(cpp),'-o',str(dll)]
    result=subprocess.run(cmd,capture_output=True,text=True)
    (out/'build.log').write_text(json.dumps(cmd)+'\n'+result.stdout+result.stderr,encoding='utf-8');result.check_returncode()
    lib=ctypes.CDLL(str(dll.resolve()));f=lib.ref_voxel
    fp=np.ctypeslib.ndpointer(dtype=np.float32,flags='C_CONTIGUOUS');ip=np.ctypeslib.ndpointer(dtype=np.int32,flags='C_CONTIGUOUS')
    f.argtypes=[fp,ctypes.c_int,ctypes.c_int,fp,ip,ip,fp,fp,ctypes.c_int,ctypes.c_int];f.restype=ctypes.c_int
    size=np.array([.16,.16,4],dtype='f4');bounds=np.array([0,-39.68,-3,69.12,39.68,1],dtype='f4')
    op=Voxelization(size,bounds,32,(16000,40000)).eval()
    cases=[('kitti',np.fromfile(ROOT/'artifacts/upstream/000134.bin',dtype='<f4').reshape(-1,4))]
    mf=json.loads((ROOT/'artifacts/det02_foreground_r1/manifest.json').read_text(encoding='utf-8'))
    for s in mf['sessions']:
        fr=s['frames'][len(s['frames'])//2]
        for variant in ['A_full','B_workspace','C_reference','E_cleanup']:
            p=np.fromfile(ROOT/'artifacts/det02_foreground_r1'/s['sid']/fr['variants'][variant]['file'],dtype='<f4').reshape(-1,4)
            p[:,2]-=np.float32(1.73);p[:,3]/=np.float32(1023);cases.append((s['sid']+'_'+variant,p))
    edge=np.array([[0,-39.68,-3,1],[.16,0,-2,2],[69.12,0,-2,3],[2,39.68,-2,4],
                   [2,0,1,5],[np.nextafter(bounds[3],np.float32(0)),0,-2,6]],dtype='f4')
    cases.append(('boundaries',edge))
    records=[]
    for name,p in cases:
        v=np.zeros((40000,32,4),dtype='f4');c=np.zeros((40000,3),dtype='i4');n=np.zeros(40000,dtype='i4')
        num=f(p,len(p),4,v,c,n,size,bounds,32,40000)
        ours=op(torch.from_numpy(p));native=(v[:num],c[:num,::-1],n[:num])
        eq=[np.array_equal(x.numpy(),y) for x,y in zip(ours,native)]
        row=dict(case=name,input_sha256=__import__('hashlib').sha256(p.tobytes()).hexdigest(),exact_voxels_coords_counts=eq,
                 native_voxels=num,adapter_voxels=len(ours[0]))
        if not all(eq):row.update(adapter_coords=ours[1].tolist(),native_coords=native[1].tolist())
        records.append(row)
    report=dict(source_sha256=sha(source),host_cpp_sha256=sha(cpp),dll_sha256=sha(dll),command=cmd,
                cases=records,scope='Verbatim upstream dynamic/hard C++ kernel bodies with host accessor/allocation shim; not original ATen extension or GPU runtime',
                actual_gpu='BLOCKED: CPU-only torch, CUDA unavailable',original_aten_extension='BLOCKED: no MSVC toolchain; MinGW does not provide PyTorch Windows MSVC ABI')
    (out/'result.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2))


if __name__=='__main__':
    import sys
    main(Path(sys.argv[1]))
