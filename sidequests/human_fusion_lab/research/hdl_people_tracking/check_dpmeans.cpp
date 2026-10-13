#include <algorithm>
#include <cassert>
#include <iostream>
#include "include/kkl/alg/dp_means.hpp"
int main(){kkl::alg::DPmeans<float,2> dp;std::vector<Eigen::Vector2f> x;for(int i=0;i<30;i++){x.emplace_back(.001f*i,0);x.emplace_back(2+.001f*i,0);}bool ok=dp.train(x,.45f);assert(ok);assert(dp.centroids.size()>=2);assert(dp.labels[0]!=dp.labels[1]);std::cout<<"PINNED_UPSTREAM_DP_MEANS_PASS clusters="<<dp.centroids.size()<<std::endl;}
