#include "publish_manager.h"
#include <cmath>
#if ROS_FOUND==1
#include <ros/ros.h>
#include <sensor_msgs/point_cloud2_iterator.h>
#include <sensor_msgs/PointCloud.h>
#include <inno_lidar_msg/DeviceStatus.h>
#ifdef ENABLE_IMU_MSG_PARSE
#include <sensor_msgs/Imu.h>
#endif
#else
#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/point_cloud2_iterator.hpp>
#include "inno_lidar_msg/msg/device_status.hpp"
#include <sstream>
#ifdef ENABLE_IMU_MSG_PARSE
#include <sensor_msgs/msg/imu.hpp>
#endif
#endif
#if ROS_FOUND==1
typedef sensor_msgs::PointCloud2 LidarCloud2;
typedef sensor_msgs::PointField  LidarField;
typedef sensor_msgs::Imu         IMU;
typedef inno_lidar_msg::DeviceStatus DeviceStatus;
#else
typedef sensor_msgs::msg::PointCloud2 LidarCloud2;
typedef sensor_msgs::msg::PointField  LidarField;
typedef sensor_msgs::msg::Imu         IMU;
typedef inno_lidar_msg::msg::DeviceStatus DeviceStatus;
#endif
namespace innolight
{
namespace lidar
{
struct PublishManager::Impl
{
public:
    Impl()
    {

    }
    // Device source stamps are consumed in seconds (runtime evidence; the SDK
    // header comment claiming nanoseconds is not verified, so the unit is not
    // changed). Non-finite/negative/out-of-range values become the invalid
    // (0,0) stamp and the fractional-second rounding carries at 1e9 so no
    // invalid ROS nsec/nanosec (>= 1e9) can be published. The legal second
    // range follows the actual ROS field: ros::Time.sec is uint32 under ROS1,
    // while ROS2 builtin_interfaces/Time.sec is int32; the range check runs on
    // the whole second and again after the nanosecond carry.
    static void deviceStampToRos(double timestamp, uint32_t& sec, uint32_t& nsec)
    {
        sec = 0;
        nsec = 0;
#if ROS_FOUND==1
        const double max_sec = 4294967295.0;
#else
        const double max_sec = 2147483647.0;
#endif
        if (!std::isfinite(timestamp) || timestamp < 0.0)
        {
            return;
        }
        double whole = floor(timestamp);
        if (whole > max_sec)
        {
            return;
        }
        uint32_t nano = (uint32_t)round((timestamp - whole) * 1e9);
        if (nano >= 1000000000u)
        {
            if (whole + 1.0 > max_sec)
            {
                return;
            }
            nano -= 1000000000u;
            whole += 1.0;
        }
        sec = (uint32_t)whole;
        nsec = nano;
    }
    inline DeviceStatus toRosDeviceStatus(const RosPointCloud& inno_msg,const std::string& frame_id)
    {
        DeviceStatus msg;
        msg.header.frame_id = frame_id;
        uint32_t stamp_sec = 0;
        uint32_t stamp_nsec = 0;
        deviceStampToRos(inno_msg.timestamp, stamp_sec, stamp_nsec);
        msg.header.stamp.sec = stamp_sec;
        //std::cout<<"inno_msg.timestamp:"<<inno_msg.timestamp<<std::endl;
#if ROS_FOUND==1
        msg.header.seq = inno_msg.seq;
        msg.header.stamp.nsec = stamp_nsec;
#else
        msg.header.stamp.nanosec = stamp_nsec;
#endif
        msg.device_number=inno_msg.device_number;
        msg.trx_temperature=inno_msg.trx_temperature;
        msg.main_temperature=inno_msg.main_temperature;
        msg.abnormal_flag=inno_msg.abnormal_flag;
        return msg;
    }
    inline LidarCloud2 toRosMsg(const RosPointCloud& inno_msg, const std::string& frame_id, bool send_by_rows)
    {
        LidarCloud2 ros_msg;
        int fields =5;
#ifdef POINT_TYPE_TIME
        fields = 6;
#elif defined(POINT_TYPE_SOURCE)
        fields = 10;
#else
#endif
        ros_msg.fields.clear();
        ros_msg.fields.reserve(fields);
        ros_msg.width = inno_msg.points.size(); 
        ros_msg.height = 1; 
  
        int offset = 0;
        offset = addPointField(ros_msg, "x", 1, LidarField::FLOAT32, offset);
        offset = addPointField(ros_msg, "y", 1, LidarField::FLOAT32, offset);
        offset = addPointField(ros_msg, "z", 1, LidarField::FLOAT32, offset);
        offset = addPointField(ros_msg, "intensity", 1, LidarField::FLOAT32, offset);
        offset = addPointField(ros_msg, "ring", 1, LidarField::UINT16, offset);
#ifdef POINT_TYPE_TIME  
        offset = addPointField(ros_msg, "timestamp", 1, LidarField::FLOAT64, offset);
#elif defined(POINT_TYPE_SOURCE)
        offset = addPointField(ros_msg, "timestamp", 1, LidarField::FLOAT64, offset);
        offset = addPointField(ros_msg, "distance", 1, LidarField::UINT32, offset);
        offset = addPointField(ros_msg, "horizontal", 1, LidarField::UINT32, offset);
        offset = addPointField(ros_msg, "vertical", 1, LidarField::UINT32, offset);
        offset = addPointField(ros_msg, "speed", 1, LidarField::UINT8, offset);
#else
#endif
        ros_msg.point_step = offset;
        ros_msg.row_step = ros_msg.width * ros_msg.point_step;
        ros_msg.is_dense = inno_msg.is_dense;
        ros_msg.data.resize(ros_msg.point_step * ros_msg.width * ros_msg.height);
        sensor_msgs::PointCloud2Iterator<float> iter_x(ros_msg, "x");
        sensor_msgs::PointCloud2Iterator<float> iter_y(ros_msg, "y");
        sensor_msgs::PointCloud2Iterator<float> iter_z(ros_msg, "z");
        sensor_msgs::PointCloud2Iterator<float> iter_intensity(ros_msg, "intensity");
        sensor_msgs::PointCloud2Iterator<uint16_t> iter_ring(ros_msg, "ring");
#ifdef POINT_TYPE_TIME
        sensor_msgs::PointCloud2Iterator<double> iter_timestamp(ros_msg, "timestamp");
#elif defined(POINT_TYPE_SOURCE)
        sensor_msgs::PointCloud2Iterator<double> iter_timestamp(ros_msg, "timestamp");
        sensor_msgs::PointCloud2Iterator<uint32_t> iter_distance(ros_msg, "distance");
        sensor_msgs::PointCloud2Iterator<uint32_t> iter_horizontal(ros_msg, "horizontal");
        sensor_msgs::PointCloud2Iterator<uint32_t> iter_vertical(ros_msg, "vertical");
        sensor_msgs::PointCloud2Iterator<uint8_t> iter_speed(ros_msg, "speed");
#else
#endif
        for (auto &point:inno_msg.points)
        {
            *iter_x = point.x;
            *iter_y = point.y;
            *iter_z = point.z;
            *iter_intensity = point.intensity;
            *iter_ring = point.ring;
            ++iter_x;
            ++iter_y;;
            ++iter_z;
            ++iter_intensity;
            ++iter_ring;
#ifdef POINT_TYPE_TIME
            *iter_timestamp = point.timestamp;
            ++iter_timestamp;
#elif defined(POINT_TYPE_SOURCE)
            *iter_timestamp = point.timestamp;
            *iter_distance = point.distance;
            *iter_horizontal = point.horizontal;
            *iter_vertical = point.vertical;
            *iter_speed = point.speed;
            ++iter_timestamp;
            ++iter_distance;
            ++iter_horizontal;
            ++iter_vertical;
            ++iter_speed;
#endif
        }
        ros_msg.header.frame_id = frame_id;
        //ros_msg.header.stamp=ros::Time()::now();
        //ros_msg.header.stamp=std::chrono::system_clock::now();
        //ros_msg.header.stamp = ros_msg.header.stamp.fromSec(inno_msg.timestamp);

        uint32_t stamp_sec = 0;
        uint32_t stamp_nsec = 0;
        deviceStampToRos(inno_msg.timestamp, stamp_sec, stamp_nsec);
        ros_msg.header.stamp.sec = stamp_sec;
        //std::cout<<"inno_msg.timestamp:"<<inno_msg.timestamp<<std::endl;
#if ROS_FOUND==1
        ros_msg.header.seq = inno_msg.seq;
        ros_msg.header.stamp.nsec = stamp_nsec;
#else
        ros_msg.header.stamp.nanosec = stamp_nsec;
#endif
        ros_msg.header.frame_id = frame_id;
        return ros_msg;
    }
#ifdef ENABLE_IMU_MSG_PARSE
    IMU toRosMsg(const std::shared_ptr<ImuMsg>& msg, const std::string& frame_id)
    {
        IMU imu_msg;
        uint32_t stamp_sec = 0;
        uint32_t stamp_nsec = 0;
        deviceStampToRos(msg->timestamp, stamp_sec, stamp_nsec);
        imu_msg.header.stamp.sec = stamp_sec;
#if ROS_FOUND==1
        imu_msg.header.stamp.nsec = stamp_nsec;
#else
        imu_msg.header.stamp.nanosec = stamp_nsec;
#endif
        imu_msg.header.frame_id = frame_id;
        // Set IMU data
        imu_msg.angular_velocity.x = msg->angular_velocity_x;
        imu_msg.angular_velocity.y = msg->angular_velocity_y;
        imu_msg.angular_velocity.z = msg->angular_velocity_z;

        imu_msg.linear_acceleration.x = msg->linear_acceleration_x;
        imu_msg.linear_acceleration.y = msg->linear_acceleration_y;
        imu_msg.linear_acceleration.z = msg->linear_acceleration_z;
        // The SDK orientation/state semantics are not verified and no valid
        // quaternion is copied, so declare "orientation not provided" with the
        // ROS covariance[0] = -1 convention instead of publishing an illegal
        // all-zero orientation with unknown covariance.
        for (auto &covariance : imu_msg.orientation_covariance)
        {
            covariance = 0.0;
        }
        imu_msg.orientation_covariance[0] = -1.0;
        return imu_msg;
    }
#endif
    void Init(const YAML::Node& config)
    {
        yamlRead<bool>(config["ros"], "ros_send_by_rows", m_send_by_rows, false);
        bool dense_points;
        yamlRead<bool>(config["driver"], "dense_points", dense_points, false);
        if (dense_points)
            m_send_by_rows = false;
        yamlRead<std::string>(config["ros"],"ros_frame_id", m_frame_id, "innolidar");
        std::string ros_send_topic;
        yamlRead<std::string>(config["ros"],"ros_send_point_cloud_topic", ros_send_topic, "innolidar_points");
        static int node_index = 0;
        std::stringstream node_name;
        node_name << "inno_points_destination_" << node_index++;
        
        std::string ros_device_status_send_topic;
        yamlRead<std::string>(config["ros"],"ros_device_status_send_topic", ros_device_status_send_topic, "device_status");
        //m_node_ptr=std::make_shared<rclcpp::Node>(node_name.str());
#if ROS_FOUND==1
        m_nh = std::unique_ptr<ros::NodeHandle>(new ros::NodeHandle());
        m_pub = m_nh->advertise<sensor_msgs::PointCloud2>(ros_send_topic, 100);
        m_device_status_pub=m_nh->advertise<DeviceStatus>(ros_device_status_send_topic,100);
#ifdef ENABLE_IMU_MSG_PARSE
        std::string ros_send_imu_data_topic;
        yamlRead<std::string>(config["ros"],"ros_send_imu_topic", ros_send_imu_data_topic, "inno_imu");
        m_imu_pub = m_nh->advertise<sensor_msgs::Imu>(ros_send_imu_data_topic, 200);
#endif
#else
        m_nh=std::make_shared<rclcpp::Node>(node_name.str());
        m_pub = m_nh->create_publisher<sensor_msgs::msg::PointCloud2>(ros_send_topic, 100);
        m_device_status_pub=m_nh->create_publisher<DeviceStatus>(ros_device_status_send_topic, 100);
#ifdef ENABLE_IMU_MSG_PARSE
        std::string ros_send_imu_data_topic;
        yamlRead<std::string>(config["ros"],"ros_send_imu_topic", ros_send_imu_data_topic, "inno_imu");
        m_imu_pub = m_nh->create_publisher<sensor_msgs::msg::Imu>(ros_send_imu_data_topic, 200);
#endif
#endif
    }
    void SendPointCloud(const RosPointCloud& msg)
    {
#if ROS_FOUND==1
        m_pub.publish(toRosMsg(msg, m_frame_id, m_send_by_rows)); 
        m_device_status_pub.publish(toRosDeviceStatus(msg,m_frame_id));
#else
        m_pub->publish(toRosMsg(msg, m_frame_id, m_send_by_rows));
        m_device_status_pub->publish(toRosDeviceStatus(msg,m_frame_id));
#endif
    }
    void SendImuMsg(const std::shared_ptr<ImuMsg>& msg)
    {
#ifdef ENABLE_IMU_MSG_PARSE
#if ROS_FOUND==1
        m_imu_pub.publish(toRosMsg(msg, m_frame_id)); 
#else
        m_imu_pub->publish(toRosMsg(msg, m_frame_id));
#endif
#endif
    
    }
private:
#if ROS_FOUND==1
    std::shared_ptr<ros::NodeHandle> m_nh;
    ros::Publisher  m_pub;
    ros::Publisher  m_device_status_pub;
#ifdef ENABLE_IMU_MSG_PARSE
    ros::Publisher m_imu_pub; 
#endif
#else
    std::shared_ptr<rclcpp::Node>    m_nh;
    rclcpp::Publisher<sensor_msgs::msg::PointCloud2>::SharedPtr m_pub;
    rclcpp::Publisher<DeviceStatus>::SharedPtr m_device_status_pub;
#ifdef ENABLE_IMU_MSG_PARSE
  rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr m_imu_pub;
#endif
#endif
    std::string m_frame_id;
    bool m_send_by_rows;
};

PublishManager::PublishManager()
:m_impl(std::make_shared<PublishManager::Impl>())
{

}

PublishManager::~PublishManager()
{
    m_impl.reset();
    m_impl=nullptr;
}
void PublishManager::Init(const YAML::Node& config)
{
    m_impl->Init(config);
}
void PublishManager::SendPointCloud(const RosPointCloud& msg)
{
    m_impl->SendPointCloud(msg);
}
#ifdef ENABLE_IMU_MSG_PARSE
void PublishManager::SendImuMsg(const std::shared_ptr<ImuMsg>& msg)
{
    m_impl->SendImuMsg(msg);
}
#endif
}
}
