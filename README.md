# OM1 - Modular AI Runtime for Robots

<div align="center">

[English](#english) | [中文](#中文) | [Tiếng Việt](#tiếng-việt)

[![Technical Paper](https://img.shields.io/badge/Technical-Paper-blue)](https://openmind.org) 
[![Documentation](https://img.shields.io/badge/Docs-docs.openmind.org-green)](https://docs.openmind.org)
[![Discord](https://img.shields.io/badge/Discord-Join-purple)](https://discord.gg/openmind)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

</div>

---

<a name="english"></a>

![OM_Banner_X2](https://user-images.githubusercontent.com/placeholder/om_banner.png)

**[Technical Paper](https://openmind.org)** | **[Documentation](https://docs.openmind.org)** | **[X/Twitter](https://x.com/openmind_agi)** | **[Discord](https://discord.gg/openmind)**

**OpenMind's OM1 is a modular AI runtime that empowers developers to create and deploy multimodal AI agents across digital environments and physical robots**, including Humanoids, Phone Apps, websites, Quadrupeds, and educational robots such as TurtleBot 4. OM1 agents can process diverse inputs like web data, social media, camera feeds, and LIDAR, while enabling physical actions including motion, autonomous navigation, and natural conversations. The goal of OM1 is to make it easy to create highly capable human-focused robots, that are easy to upgrade and (re)configure to accommodate different physical form factors.

## Capabilities of OM1

* **Modular Architecture**: Designed with Python for simplicity and seamless integration.
* **Data Input**: Easily handles new data and sensors.
* **Hardware Support via Plugins**: Supports new hardware through plugins for API endpoints and specific robot hardware connections to `ROS2`, `Zenoh`, and `CycloneDDS`. (We recommend `Zenoh` for all new development).
* **Web-Based Debugging Display**: Monitor the system in action with WebSim (available at http://localhost:8000/) for easy visual debugging.
* **Pre-configured Endpoints**: Supports Voice-to-Speech, OpenAI's `gpt-4o`, DeepSeek, and multiple Visual Language Models (VLMs) with pre-configured endpoints for each service.

## Architecture Overview

![Architecture](https://user-images.githubusercontent.com/placeholder/architecture.png)

## Getting Started - Hello World

To get started with OM1, let's run the Spot agent. Spot uses your webcam to capture and label objects. These text captions are then sent to `OpenAI 4o`, which returns `movement`, `speech` and `face` action commands. These commands are displayed on WebSim along with basic timing and other debugging information.

### Package Management and VENV

You will need the uv package manager.

### Clone the Repo

```bash
git clone https://github.com/openmind/OM1.git
cd OM1
git submodule update --init
uv venv
```

### Install Dependencies

**For MacOS:**

```bash
brew install portaudio ffmpeg
```

**For Linux:**

```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python-dev ffmpeg
```

### Obtain an OpenMind API Key

Obtain your API Key at [OpenMind Portal](https://portal.openmind.org). Copy it to `config/spot.json5`, replacing the `openmind_free` placeholder. Or, `cp env.example .env` and add your key to the `.env`.

### Launching OM1

```bash
uv run src/run.py spot
```

After launching OM1, the Spot agent will interact with you and perform (simulated) actions. For more help connecting OM1 to your robot hardware, see [getting started](https://docs.openmind.org/getting-started).

## What's Next?

* Try out some [examples](https://docs.openmind.org/examples)
* Add new `inputs` and `actions`.
* Design custom agents and robots by creating your own `json5` config files with custom combinations of inputs and actions.
* Change the system prompts in the configuration files (located in `/config/`) to create new behaviors.

## Interfacing with New Robot Hardware

OM1 assumes that robot hardware provides a high-level SDK that accepts elemental movement and action commands such as `backflip`, `run`, `gently pick up the red apple`, `move(0.37, 0, 0)`, and `smile`. An example is provided in `actions/move_safe/connector/ros2.py`:

```python
...
elif output_interface.action == "shake paw":
    if self.sport_client:
        self.sport_client.Hello()
...
```

If your robot hardware does not yet provide a suitable HAL (hardware abstraction layer), traditional robotics approaches such as RL (reinforcement learning) in concert with suitable simulation environments (Unity, Gazebo), sensors (such as hand mounted ZED depth cameras), and custom VLAs will be needed for you to create one. It is further assumed that your HAL accepts motion trajectories, provides battery and thermal management/monitoring, and calibrates and tunes sensors such as IMUs, LIDARs, and magnetometers.

OM1 can interface with your HAL via USB, serial, ROS2, CycloneDDS, Zenoh, or websockets. For an example of an advanced humanoid HAL, please see [Unitree's C++ SDK](https://github.com/unitreerobotics). Frequently, a HAL, especially ROS2 code, will be dockerized and can then interface with OM1 through DDS middleware or websockets.

## Recommended Development Platforms

OM1 is developed on:

* Jetson AGX Orin 64GB (running Ubuntu 22.04 and JetPack 6.1)
* Mac Studio with Apple M2 Ultra with 48 GB unified memory (running MacOS Sequoia)
* Mac Mini with Apple M4 Pro with 48 GB unified memory (running MacOS Sequoia)
* Generic Linux machines (running Ubuntu 22.04)

OM1 _should_ run on other platforms (such as Windows) and microcontrollers such as the Raspberry Pi 5 16GB.

## Full Autonomy Guidance

We're excited to introduce **full autonomy mode**, where three services work together in a loop without manual intervention:

* **om1**
* **unitree_go2_ros2_sdk** – A ROS 2 package that provides SLAM (Simultaneous Localization and Mapping) capabilities for the Unitree Go2 robot using an RPLiDAR sensor, the SLAM Toolbox and the Nav2 stack.
* **om1-avatar** – A modern React-based frontend application that provides the user interface and avatar display system for OM1 robotics software.

## Intro to Backpack

From research to real-world autonomy, a platform that learns, moves, and builds with you. We'll shortly be releasing the **BOM** and details on **DIY** for it. Stay tuned!

Clone the following repos:

* https://github.com/OpenMind/OM1.git
* https://github.com/OpenMind/unitree_go2_ros2_sdk.git
* https://github.com/OpenMind/OM1-avatar.git

## Starting the System

To start all services, run the following commands:

### For OM1

Setup the API key:

For Bash: `vim ~/.bashrc` or `~/.bash_profile`.

For Zsh: `vim ~/.zshrc`.

Add:

```bash
export OM_API_KEY="your_api_key"
```

Update the docker-compose file. Replace "unitree_go2_autonomy_advance" with the agent you want to run:

```yaml
command: ["unitree_go2_autonomy_advance"]
```

```bash
cd OM1
docker-compose up om1 -d --no-build
```

### For unitree_go2_ros2_sdk

```bash
cd unitree_go2_ros2_sdk
docker-compose up orchestrator -d --no-build
docker-compose up om1_sensor -d --no-build
docker-compose up watchdog -d --no-build
```

### For OM1-avatar

```bash
cd OM1-avatar
docker-compose up om1_avatar -d --no-build
```

## Detailed Documentation

More detailed documentation can be accessed at [docs.openmind.org](https://docs.openmind.org).

## Contributing

Please make sure to read the [Contributing Guide](CONTRIBUTING.md) before making a pull request.

## License

This project is licensed under the terms of the [MIT License](LICENSE), which is a permissive free software license that allows users to freely use, modify, and distribute the software. The MIT License is a widely used and well-established license that is known for its simplicity and flexibility. By using the MIT License, this project aims to encourage collaboration, modification, and distribution of the software.

---

<a name="中文"></a>

# OM1 - 模块化机器人AI运行时

**[English](#english)** | **中文** | **[Tiếng Việt](#tiếng-việt)**

![OM_Banner_X2](https://user-images.githubusercontent.com/placeholder/om_banner.png)

**[技术论文](https://openmind.org)** | **[文档](https://docs.openmind.org)** | **[X/Twitter](https://x.com/openmind_agi)** | **[Discord](https://discord.gg/openmind)**

**OpenMind 的 OM1 是一个模块化 AI 运行时，使开发者能够在数字环境和物理机器人上创建和部署多模态 AI 智能体**，包括人形机器人、手机应用、网站、四足机器人以及 TurtleBot 4 等教育机器人。OM1 智能体可以处理网络数据、社交媒体、摄像头画面和激光雷达等多样化输入，同时支持运动、自主导航和自然对话等物理动作。OM1 的目标是让创建高性能、以人为本的机器人变得简单，并且易于升级和（重新）配置以适应不同的物理形态。

## OM1 的能力

* **模块化架构**：采用 Python 设计，简单且无缝集成。
* **数据输入**：轻松处理新数据和传感器。
* **通过插件支持硬件**：通过插件支持新硬件，包括 API 端点以及与 `ROS2`、`Zenoh` 和 `CycloneDDS` 的特定机器人硬件连接。（我们建议所有新开发使用 `Zenoh`）。
* **基于 Web 的调试显示**：通过 WebSim（可在 http://localhost:8000/ 访问）监控系统运行，便于可视化调试。
* **预配置端点**：支持语音转文本、OpenAI 的 `gpt-4o`、DeepSeek 以及多个视觉语言模型（VLM），每个服务都有预配置端点。

## 架构概述

![架构图](https://user-images.githubusercontent.com/placeholder/architecture.png)

## 入门 - Hello World

要开始使用 OM1，让我们运行 Spot 智能体。Spot 使用您的网络摄像头捕获和标记物体。这些文本描述随后发送到 `OpenAI 4o`，后者返回 `运动`、`语音` 和 `表情` 动作命令。这些命令会在 WebSim 上显示，同时显示基本的时间和其他调试信息。

### 包管理和虚拟环境

您需要 uv 包管理器。

### 克隆仓库

```bash
git clone https://github.com/openmind/OM1.git
cd OM1
git submodule update --init
uv venv
```

### 安装依赖

**MacOS：**

```bash
brew install portaudio ffmpeg
```

**Linux：**

```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python-dev ffmpeg
```

### 获取 OpenMind API 密钥

在 [OpenMind Portal](https://portal.openmind.org) 获取您的 API 密钥。将其复制到 `config/spot.json5`，替换 `openmind_free` 占位符。或者执行 `cp env.example .env` 并将密钥添加到 `.env` 文件中。

### 启动 OM1

```bash
uv run src/run.py spot
```

启动 OM1 后，Spot 智能体将与您互动并执行（模拟）动作。有关将 OM1 连接到机器人硬件的更多帮助，请参阅[入门指南](https://docs.openmind.org/getting-started)。

## 下一步做什么？

* 尝试一些[示例](https://docs.openmind.org/examples)
* 添加新的 `输入` 和 `动作`。
* 通过创建自己的 `json5` 配置文件来设计定制智能体和机器人，使用输入和动作的自定义组合。
* 修改配置文件（位于 `/config/` 目录）中的系统提示词以创建新行为。

## 与新机器人硬件对接

OM1 假设机器人硬件提供高级 SDK，可接受基本运动和动作命令，如 `后空翻`、`奔跑`、`轻轻拿起红苹果`、`move(0.37, 0, 0)` 和 `微笑`。`actions/move_safe/connector/ros2.py` 中提供了一个示例：

```python
...
elif output_interface.action == "shake paw":
    if self.sport_client:
        self.sport_client.Hello()
...
```

如果您的机器人硬件尚未提供合适的 HAL（硬件抽象层），则需要使用传统机器人方法，如强化学习（RL），配合合适的仿真环境（Unity、Gazebo）、传感器（如手部安装的 ZED 深度相机）和自定义视觉语言动作模型（VLA）来创建。此外，假设您的 HAL 接受运动轨迹，提供电池和热管理/监控，并校准和调整 IMU、激光雷达和磁力计等传感器。

OM1 可以通过 USB、串口、ROS2、CycloneDDS、Zenoh 或 websockets 与您的 HAL 接口。有关高级人形机器人 HAL 的示例，请参阅 [Unitree 的 C++ SDK](https://github.com/unitreerobotics)。通常，HAL（特别是 ROS2 代码）会被 Docker 化，然后可以通过 DDS 中间件或 websockets 与 OM1 接口。

## 推荐的开发平台

OM1 在以下平台上开发：

* Jetson AGX Orin 64GB（运行 Ubuntu 22.04 和 JetPack 6.1）
* Mac Studio，搭载 Apple M2 Ultra 和 48 GB 统一内存（运行 MacOS Sequoia）
* Mac Mini，搭载 Apple M4 Pro 和 48 GB 统一内存（运行 MacOS Sequoia）
* 通用 Linux 机器（运行 Ubuntu 22.04）

OM1 应该可以在其他平台（如 Windows）和微控制器（如 Raspberry Pi 5 16GB）上运行。

## 完全自主模式指南

我们很高兴推出**完全自主模式**，其中三个服务在无需人工干预的情况下循环协同工作：

* **om1**
* **unitree_go2_ros2_sdk** – 一个 ROS 2 软件包，使用 RPLiDAR 传感器、SLAM Toolbox 和 Nav2 栈为 Unitree Go2 机器人提供 SLAM（同步定位与地图构建）能力。
* **om1-avatar** – 一个现代的基于 React 的前端应用程序，为 OM1 机器人软件提供用户界面和头像显示系统。

## Backpack 简介

从研究到真实世界的自主性，一个与您一起学习、移动和构建的平台。我们将很快发布**物料清单（BOM）**和**DIY** 详情。敬请期待！

克隆以下仓库：

* https://github.com/OpenMind/OM1.git
* https://github.com/OpenMind/unitree_go2_ros2_sdk.git
* https://github.com/OpenMind/OM1-avatar.git

## 启动系统

要启动所有服务，请运行以下命令：

### OM1

设置 API 密钥：

对于 Bash：`vim ~/.bashrc` 或 `~/.bash_profile`。

对于 Zsh：`vim ~/.zshrc`。

添加：

```bash
export OM_API_KEY="your_api_key"
```

更新 docker-compose 文件。将 "unitree_go2_autonomy_advance" 替换为您要运行的智能体：

```yaml
command: ["unitree_go2_autonomy_advance"]
```

```bash
cd OM1
docker-compose up om1 -d --no-build
```

### unitree_go2_ros2_sdk

```bash
cd unitree_go2_ros2_sdk
docker-compose up orchestrator -d --no-build
docker-compose up om1_sensor -d --no-build
docker-compose up watchdog -d --no-build
```

### OM1-avatar

```bash
cd OM1-avatar
docker-compose up om1_avatar -d --no-build
```

## 详细文档

更详细的文档可以在 [docs.openmind.org](https://docs.openmind.org) 访问。

## 贡献

在提交 pull request 之前，请务必阅读[贡献指南](CONTRIBUTING.md)。

## 许可证

本项目根据 [MIT 许可证](LICENSE)的条款授权，这是一种宽松的自由软件许可证，允许用户自由使用、修改和分发软件。MIT 许可证是一种广泛使用且成熟的许可证，以其简单性和灵活性而闻名。通过使用 MIT 许可证，本项目旨在鼓励软件的协作、修改和分发。

---

<a name="tiếng-việt"></a>

# OM1 - Hệ Thống AI Mô-đun cho Robot

**[English](#english)** | **[中文](#中文)** | **Tiếng Việt**

![OM_Banner_X2](https://user-images.githubusercontent.com/placeholder/om_banner.png)

**[Bài báo kỹ thuật](https://openmind.org)** | **[Tài liệu](https://docs.openmind.org)** | **[X/Twitter](https://x.com/openmind_agi)** | **[Discord](https://discord.gg/openmind)**

**OM1 của OpenMind là một hệ thống AI mô-đun giúp các nhà phát triển tạo và triển khai các tác nhân AI đa phương thức trên môi trường kỹ thuật số và robot vật lý**, bao gồm Robot hình người, Ứng dụng điện thoại, trang web, Robot bốn chân và robot giáo dục như TurtleBot 4. Các tác nhân OM1 có thể xử lý nhiều đầu vào đa dạng như dữ liệu web, mạng xã hội, nguồn cấp camera và LIDAR, đồng thời cho phép các hành động vật lý bao gồm chuyển động, điều hướng tự động và hội thoại tự nhiên. Mục tiêu của OM1 là làm cho việc tạo ra các robot có khả năng cao, tập trung vào con người trở nên dễ dàng, dễ nâng cấp và (tái) cấu hình để phù hợp với các hình thái vật lý khác nhau.

## Khả năng của OM1

* **Kiến trúc mô-đun**: Được thiết kế bằng Python để đơn giản và tích hợp liền mạch.
* **Đầu vào dữ liệu**: Dễ dàng xử lý dữ liệu và cảm biến mới.
* **Hỗ trợ phần cứng qua Plugin**: Hỗ trợ phần cứng mới thông qua plugin cho các điểm cuối API và kết nối phần cứng robot cụ thể với `ROS2`, `Zenoh` và `CycloneDDS`. (Chúng tôi khuyên dùng `Zenoh` cho tất cả phát triển mới).
* **Màn hình gỡ lỗi dựa trên Web**: Giám sát hệ thống hoạt động với WebSim (có sẵn tại http://localhost:8000/) để gỡ lỗi trực quan dễ dàng.
* **Điểm cuối được cấu hình sẵn**: Hỗ trợ Giọng nói sang Văn bản, `gpt-4o` của OpenAI, DeepSeek và nhiều Mô hình Ngôn ngữ Thị giác (VLM) với các điểm cuối được cấu hình sẵn cho mỗi dịch vụ.

## Tổng quan Kiến trúc

![Kiến trúc](https://user-images.githubusercontent.com/placeholder/architecture.png)

## Bắt đầu - Hello World

Để bắt đầu với OM1, hãy chạy tác nhân Spot. Spot sử dụng webcam của bạn để chụp và gắn nhãn các đối tượng. Các chú thích văn bản này sau đó được gửi đến `OpenAI 4o`, trả về các lệnh hành động `chuyển động`, `lời nói` và `biểu cảm khuôn mặt`. Các lệnh này được hiển thị trên WebSim cùng với thông tin thời gian cơ bản và thông tin gỡ lỗi khác.

### Quản lý gói và môi trường ảo

Bạn sẽ cần trình quản lý gói uv.

### Sao chép kho lưu trữ

```bash
git clone https://github.com/openmind/OM1.git
cd OM1
git submodule update --init
uv venv
```

### Cài đặt các phụ thuộc

**Cho MacOS:**

```bash
brew install portaudio ffmpeg
```

**Cho Linux:**

```bash
sudo apt-get update
sudo apt-get install portaudio19-dev python-dev ffmpeg
```

### Lấy Khóa API OpenMind

Lấy Khóa API của bạn tại [OpenMind Portal](https://portal.openmind.org). Sao chép nó vào `config/spot.json5`, thay thế phần giữ chỗ `openmind_free`. Hoặc, `cp env.example .env` và thêm khóa của bạn vào `.env`.

### Khởi chạy OM1

```bash
uv run src/run.py spot
```

Sau khi khởi chạy OM1, tác nhân Spot sẽ tương tác với bạn và thực hiện các hành động (mô phỏng). Để được trợ giúp thêm về kết nối OM1 với phần cứng robot của bạn, hãy xem [hướng dẫn bắt đầu](https://docs.openmind.org/getting-started).

## Tiếp theo là gì?

* Thử một số [ví dụ](https://docs.openmind.org/examples)
* Thêm `đầu vào` và `hành động` mới.
* Thiết kế các tác nhân và robot tùy chỉnh bằng cách tạo các tệp cấu hình `json5` của riêng bạn với các kết hợp tùy chỉnh của đầu vào và hành động.
* Thay đổi các lời nhắc hệ thống trong các tệp cấu hình (nằm trong `/config/`) để tạo các hành vi mới.

## Giao tiếp với Phần cứng Robot Mới

OM1 giả định rằng phần cứng robot cung cấp SDK cấp cao chấp nhận các lệnh chuyển động và hành động cơ bản như `lộn nhào`, `chạy`, `nhẹ nhàng nhặt quả táo đỏ`, `move(0.37, 0, 0)` và `cười`. Một ví dụ được cung cấp trong `actions/move_safe/connector/ros2.py`:

```python
...
elif output_interface.action == "shake paw":
    if self.sport_client:
        self.sport_client.Hello()
...
```

Nếu phần cứng robot của bạn chưa cung cấp HAL (lớp trừu tượng phần cứng) phù hợp, các phương pháp robot truyền thống như RL (học tăng cường) kết hợp với môi trường mô phỏng phù hợp (Unity, Gazebo), cảm biến (như camera độ sâu ZED gắn tay) và VLA tùy chỉnh sẽ cần thiết để bạn tạo ra một. Ngoài ra, giả định rằng HAL của bạn chấp nhận quỹ đạo chuyển động, cung cấp quản lý/giám sát pin và nhiệt, và hiệu chỉnh và điều chỉnh các cảm biến như IMU, LIDAR và từ kế.

OM1 có thể giao tiếp với HAL của bạn qua USB, serial, ROS2, CycloneDDS, Zenoh hoặc websocket. Để xem ví dụ về HAL robot hình người nâng cao, vui lòng xem [C++ SDK của Unitree](https://github.com/unitreerobotics). Thường xuyên, HAL, đặc biệt là mã ROS2, sẽ được docker hóa và sau đó có thể giao tiếp với OM1 thông qua middleware DDS hoặc websocket.

## Nền tảng Phát triển Được đề xuất

OM1 được phát triển trên:

* Jetson AGX Orin 64GB (chạy Ubuntu 22.04 và JetPack 6.1)
* Mac Studio với Apple M2 Ultra với bộ nhớ thống nhất 48 GB (chạy MacOS Sequoia)
* Mac Mini với Apple M4 Pro với bộ nhớ thống nhất 48 GB (chạy MacOS Sequoia)
* Máy Linux chung (chạy Ubuntu 22.04)

OM1 _nên_ chạy trên các nền tảng khác (như Windows) và vi điều khiển như Raspberry Pi 5 16GB.

## Hướng dẫn Tự động Hoàn toàn

Chúng tôi rất vui mừng giới thiệu **chế độ tự động hoàn toàn**, trong đó ba dịch vụ hoạt động cùng nhau trong một vòng lặp mà không cần can thiệp thủ công:

* **om1**
* **unitree_go2_ros2_sdk** – Một gói ROS 2 cung cấp khả năng SLAM (Định vị và Lập bản đồ Đồng thời) cho robot Unitree Go2 sử dụng cảm biến RPLiDAR, SLAM Toolbox và ngăn xếp Nav2.
* **om1-avatar** – Một ứng dụng frontend hiện đại dựa trên React cung cấp giao diện người dùng và hệ thống hiển thị avatar cho phần mềm robot OM1.

## Giới thiệu về Backpack

Từ nghiên cứu đến tự động trong thế giới thực, một nền tảng học hỏi, di chuyển và xây dựng cùng bạn. Chúng tôi sẽ sớm phát hành **BOM** và chi tiết về **DIY** cho nó. Hãy theo dõi!

Sao chép các kho lưu trữ sau:

* https://github.com/OpenMind/OM1.git
* https://github.com/OpenMind/unitree_go2_ros2_sdk.git
* https://github.com/OpenMind/OM1-avatar.git

## Khởi động Hệ thống

Để khởi động tất cả các dịch vụ, hãy chạy các lệnh sau:

### Cho OM1

Thiết lập khóa API:

Cho Bash: `vim ~/.bashrc` hoặc `~/.bash_profile`.

Cho Zsh: `vim ~/.zshrc`.

Thêm:

```bash
export OM_API_KEY="your_api_key"
```

Cập nhật tệp docker-compose. Thay thế "unitree_go2_autonomy_advance" bằng tác nhân bạn muốn chạy:

```yaml
command: ["unitree_go2_autonomy_advance"]
```

```bash
cd OM1
docker-compose up om1 -d --no-build
```

### Cho unitree_go2_ros2_sdk

```bash
cd unitree_go2_ros2_sdk
docker-compose up orchestrator -d --no-build
docker-compose up om1_sensor -d --no-build
docker-compose up watchdog -d --no-build
```

### Cho OM1-avatar

```bash
cd OM1-avatar
docker-compose up om1_avatar -d --no-build
```

## Tài liệu Chi tiết

Tài liệu chi tiết hơn có thể được truy cập tại [docs.openmind.org](https://docs.openmind.org).

## Đóng góp

Vui lòng đảm bảo đọc [Hướng dẫn Đóng góp](CONTRIBUTING.md) trước khi thực hiện pull request.

## Giấy phép

Dự án này được cấp phép theo các điều khoản của [Giấy phép MIT](LICENSE), đây là giấy phép phần mềm tự do cho phép người dùng tự do sử dụng, sửa đổi và phân phối phần mềm. Giấy phép MIT là một giấy phép được sử dụng rộng rãi và được thiết lập tốt, nổi tiếng vì tính đơn giản và linh hoạt của nó. Bằng cách sử dụng Giấy phép MIT, dự án này nhằm khuyến khích sự hợp tác, sửa đổi và phân phối phần mềm.

---

<div align="center">

**Made with ❤️ by the OpenMind Team**

[⭐ Star us on GitHub](https://github.com/OpenMind/OM1) | [🐛 Report Issues](https://github.com/OpenMind/OM1/issues) | [💬 Join our Community](https://discord.gg/openmind)

</div>

