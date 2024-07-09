import crypt
import os
import sys
import paramiko

class SftpDB:
    def __init__(self, parent):
        self._parent = parent
        self._hostName = 'xxx.xxx.xx.xxx'
        self._port = 22
        self._userName = None
        self._password = None
        self._SSH_Client = paramiko.SSHClient()
        self.dev_id = self._parent.redisClient.configure_data.get("dev_id")

    def create_sftp_user(self):
        if sys.platform == 'linux':
            sftp_username = "user_" + self.dev_id[-4:]
            exist_user_list = os.system("awk -F':' '{ print $1}' /etc/passwd")

            priv_networks = [line for line in exist_user_list if 'user_' in line]

            os.system(f"sudo useradd {sftp_username}")
            password = self.dev_id[-17:-4]
            enc_pass = crypt.crypt(password, "22")
            os.system("useradd -p " + enc_pass + " " + sftp_username)


    def connect_sftp(self):
        try:
            self._SSH_Client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            self._SSH_Client.transport = paramiko.Transport((self._hostName, self._port))
            self._SSH_Client.connect(hostname=self._hostName, port=self._port, username=self._userName,
                                     password=self._password, look_for_keys=False)

        except Exception as e:
            print("SFTP Connection fault: ", e)
            return None
        else:
            print(f"Connected to server {self._hostName}:{self._port} as {self._userName}.")


    def disconnect_sftp(self):
        self._SSH_Client.close()
        print(f"{self._userName} is disconnected from server {self._hostName}:{self._port}")

    def execute_command(self, command):
        try:
            stdin, stdout, stderr = self._SSH_Client.exec_command(command)
            stdout.channel.recv_exit_status()
            print(stdout.read().decode())
        except Exception as e:
            print(f"Error executing command '{command}': {e}")

    def upload_files(self, remoteFilePath, localFilePath):
        temp_dir = '/tmp'
        temp_file_path_local = os.path.join(temp_dir, 'dump.rdb')
        temp_file_path_remote = os.path.join(temp_dir, 'dump.rdb')
        try:
            # permission denied hatası verdiği için öncelikle dosyayı geçici bir yere kopyala
            # os.system(
            command = f'sudo cp {localFilePath} {temp_file_path_local}'
            self.execute_command(command)

            # Dosyayı geçici bir yere kopyaladıktan sonra, sftp ile gönder
            sftp_client = self._SSH_Client.open_sftp()
            sftp_client.put(temp_file_path_local, temp_file_path_remote)
            command = f'sudo cp {temp_file_path_remote} {remoteFilePath}'
            self.execute_command(command)
            sftp_client.close()

        except Exception as e:
            print(f"Error uploading file: {e}")

    def download_files(self, remoteFilePath):
        sftp_client = self._SSH_Client.open_sftp()
        sftp_client.get(remoteFilePath, "/var/lib/redis-stack/dump.rdb")
        sftp_client.close()

    def restart_redis(self):
        commands = [
            'sudo systemctl stop redis-stack-server.service',
            'sudo systemctl start redis-stack-server.service'
        ]

        for command in commands:
            try:
                self.execute_command(command)
            except Exception as e:
                print(f"Error executing command '{command}': {e}")

    def synchronize_db(self):
        self.connect_sftp()

        local_path = '/var/lib/redis-stack/dump.rdb'
        remote_path = '/var/lib/redis-stack/dump.rdb'

        try:
            self.execute_command(f'sudo mv {remote_path} {remote_path}.backup')
        except Exception as e:
            print(f"Error renaming file: {e}")

        self.upload_files(remote_path, local_path)
        self.restart_redis()
        self.disconnect_sftp()
