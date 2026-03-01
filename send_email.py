#!/usr/bin/env python3
"""
发送贝叶斯因子库项目文件到指定邮箱
"""

import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import ssl

def send_email_with_attachment():
    """发送带附件的邮件"""
    
    # 邮件配置
    sender_email = "openclaw@henjiu.com"  # 发件人邮箱（需要配置）
    receiver_email = "43957226@qq.com"    # 收件人邮箱
    password = ""  # 需要SMTP密码
    
    # 如果没有配置密码，尝试使用默认配置
    if not password:
        print("警告: 没有配置SMTP密码")
        print("请配置以下信息:")
        print("1. SMTP服务器地址")
        print("2. SMTP端口")
        print("3. 发件人邮箱和密码")
        return False
    
    # 邮件内容
    subject = "贝叶斯因子库维护系统项目文件"
    body = """
研究员，

这是贝叶斯因子库维护系统的完整项目文件。

包含内容：
1. 正确的股票数据模拟器 (proper_simulator.py)
2. MVP贝叶斯选择器 (mvp_selector.py)
3. 集成测试代码 (test_integration.py)
4. 完整的设计文档
5. 测试结果

项目状态：迭代2完成（正确的股票数据模拟器）

核心功能：
- 精确的IC控制（误差<0.1%）
- 得分加权多空组合（杠杆2倍）
- IC方差固定，ICIR只取决于IC均值
- t期因子预测t+1期收益

测试结果：
- IC控制精度: 平均误差0.0005
- ICIR范围: 2.227到6.392
- 权重计算精度: 1e-6级别

下一步：开始迭代3（边际贡献评估）

---
OpenClaw AI Assistant
"""
    
    # 附件文件
    attachment_path = "bayesian_factor_lib_20260301_114012.tar.gz"
    
    if not os.path.exists(attachment_path):
        print(f"错误: 附件文件不存在: {attachment_path}")
        return False
    
    # 创建邮件
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject
    
    # 添加正文
    message.attach(MIMEText(body, "plain"))
    
    # 添加附件
    try:
        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        
        encoders.encode_base64(part)
        
        # 添加附件头
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {os.path.basename(attachment_path)}",
        )
        
        message.attach(part)
        print(f"附件添加成功: {attachment_path}")
        
    except Exception as e:
        print(f"添加附件失败: {e}")
        return False
    
    # 发送邮件
    try:
        # 使用QQ邮箱SMTP服务器（需要配置）
        smtp_server = "smtp.qq.com"
        smtp_port = 587  # TLS端口
        
        # 创建安全连接
        context = ssl.create_default_context()
        
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls(context=context)
            server.login(sender_email, password)
            server.send_message(message)
        
        print(f"邮件发送成功到: {receiver_email}")
        return True
        
    except Exception as e:
        print(f"邮件发送失败: {e}")
        print("\n建议的替代方案:")
        print("1. 从服务器直接下载:")
        print("   scp root@dc2.henjiu.com:/root/.openclaw/workspace-wecom-dm-caikaer/bayesian_factor_lib/bayesian_factor_lib_20260301_114012.tar.gz .")
        print("2. 使用其他邮件服务")
        print("3. 通过其他文件传输方式")
        return False

def check_email_config():
    """检查邮件配置"""
    print("检查邮件配置...")
    
    # 检查常见邮件服务配置
    configs = [
        ("/etc/postfix/main.cf", "Postfix配置"),
        ("/etc/ssmtp/ssmtp.conf", "SSMTP配置"),
        ("/etc/mail/sendmail.cf", "Sendmail配置"),
        ("~/.muttrc", "Mutt配置"),
    ]
    
    found_config = False
    for config_file, description in configs:
        expanded_path = os.path.expanduser(config_file)
        if os.path.exists(expanded_path):
            print(f"找到: {description} ({config_file})")
            found_config = True
    
    if not found_config:
        print("未找到邮件配置")
    
    return found_config

def main():
    print("=" * 60)
    print("发送贝叶斯因子库项目文件")
    print("=" * 60)
    
    # 检查配置
    if not check_email_config():
        print("\n服务器上没有配置邮件系统")
        print("无法直接发送邮件")
        
        # 提供替代方案
        print("\n替代方案:")
        print("1. 从服务器下载:")
        print("   scp root@dc2.henjiu.com:/root/.openclaw/workspace-wecom-dm-caikaer/bayesian_factor_lib/bayesian_factor_lib_20260301_114012.tar.gz .")
        print("2. 我提供关键代码片段")
        print("3. 创建Git仓库推送")
        
        return False
    
    # 尝试发送邮件
    print("\n尝试发送邮件...")
    success = send_email_with_attachment()
    
    if not success:
        print("\n邮件发送失败，请使用替代方案")
    
    return success

if __name__ == "__main__":
    main()