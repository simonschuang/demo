# reference
# https://github.com/NetApp/ontap-rest-python
#
# UnitTest: pytest -o log_cli=true -o log_cli_level=info -v .
import requests
import time
from mlsteam.log import logger
ONTEP_API_TIMEOUT = 5


class NetappOntap:
    def __init__(self, host_ip, svm_name, api_pass):
        if not api_pass:
            raise ValueError("api_pass not defined for Netapp driver")
        if not svm_name:
            raise ValueError("svm_name not defined for Netapp driver")
        self.host_ip = host_ip
        self.api_user = "admin"
        self.api_pass = api_pass
        self.svm_name = svm_name
        self.headers = self._auth_header()
        self.data_ip = None
        self.svm_uuid = None
        self.aggr_name = None

    def _auth_header(self):
        import base64

        base64string = (
            base64.encodebytes(("%s:%s" % (self.api_user, self.api_pass)).encode())
            .decode()
            .replace("\n", "")
        )
        headers = {
            "authorization": "Basic %s" % base64string,
            "content-type": "application/json",
            "accept": "application/json",
        }
        return headers

    def init(self):
        # fetch data interface
        self._fetch_interface()
        self._fetch_svm_aggregation()

    def _fetch_interface(self):
        try:
            url = "https://{}/api/network/ip/interfaces?svm.name={}&services=data_nfs&fields=ip".format(
                self.host_ip, self.svm_name
            )
            res_text = requests.get(url, headers=self.headers, timeout=ONTEP_API_TIMEOUT, verify=False).json()
            if "error" in res_text:
                raise ValueError(res_text["error"])
            for interface in res_text["records"]:
                self.data_ip = interface["ip"]["address"]
                break
        except Exception as e:
            logger.error("NetappDriver fetch interfaces failed, {}".format(e))
        if not self.data_ip:
            print("interfaces: {}".format(res_text))
            raise ValueError("can not find Netapp data address")
        logger.info("Netapp driver initialized, data address: {}".format(self.data_ip))

    def _fetch_svm_aggregation(self):
        try:
            self.svm_uuid = self._get_key_svm()
            url = "https://{}/api/svm/svms/{}".format(self.host_ip, self.svm_uuid)
            res_text = requests.get(url, headers=self.headers, timeout=ONTEP_API_TIMEOUT, verify=False).json()
            if "error" in res_text:
                raise ValueError(res_text["error"])
            # fetch
            for aggregate in res_text["aggregates"]:
                self.aggr_name = aggregate["name"]
                break
        except Exception as e:
            logger.error("NetappDriver fetch aggregate failed, {}".format(e))
        if not self.aggr_name:
            raise ValueError(
                "NetappDriver can not find svm {} aggregate name".format(self.svm_name)
            )
        logger.info(
            "Netapp driver initialization, svm aggregate name: {}".format(
                self.aggr_name
            )
        )

    def _get_key_svm(self):
        try:
            _url = "https://{}/api/svm/svms?name={}".format(
                self.host_ip, self.svm_name
            )
            svms_info = requests.get(_url, headers=self.headers, timeout=ONTEP_API_TIMEOUT, verify=False).json()
            for svm in svms_info["records"]:
                return svm["uuid"]
        except Exception as e:
            raise ValueError("NetappDriver get svm key failed, {}".format(e)) from e

    def list_volume(self):
        try:
            volumes = []
            url = "https://{}/api/storage/volumes?svm.name={}".format(
                self.host_ip, self.svm_name
            )
            volumes_info = requests.get(url, headers=self.headers, timeout=ONTEP_API_TIMEOUT,
                                        verify=False).json()
            if "error" in volumes_info:
                raise ValueError(volumes_info["error"])
            for volume in volumes_info["records"]:
                volumes.append(volume["name"])
            return volumes
        except Exception as e:
            logger.error("NetappDriver list volume failed, {}".format(e))
            raise e

    def create_volume(self, volume_name, quota):
        # GB to bytes
        if quota is None:
            quota = 0
        quota = int(quota) if not isinstance(quota, int) else quota
        provision_size = quota * 1024 * 1024 * 1024
        volume_data = {
            "svm": {"name": self.svm_name},
            "aggregates": [{"name": self.aggr_name}],
            "name": volume_name.replace(
                "-", "_"
            ),  # Netapp only support alphabet and '_'
            "size": provision_size,
            "nas": {
                "path": "/" + volume_name,
                "security_style": "unix",
                "unix_permissions": "0755",
            },
        }
        try:
            url = "https://{}/api/storage/volumes".format(self.host_ip)
            res_text = requests.post(
                url, headers=self.headers, timeout=ONTEP_API_TIMEOUT, json=volume_data, verify=False
            ).json()
            if "error" in res_text:
                raise ValueError(res_text["error"])
        except Exception as e:
            logger.error("NetappDriver create volume failed, {}".format(e))
            raise e
        self._check_job_status(res_text["job"]["uuid"])

    def _check_job_status(self, job_uuid):
        err_msg = ""
        while True:
            job_status_url = "https://{}/api/cluster/jobs/{}".format(
                self.host_ip, job_uuid
            )
            try:
                job_status = requests.get(
                    job_status_url, headers=self.headers, timeout=ONTEP_API_TIMEOUT, verify=False
                ).json()
                if job_status["state"] == "failure":
                    err_msg = f"Netapp job failed, {job_status['message']}"
                    break
                elif job_status["state"] == "success":
                    # job finished
                    break
                time.sleep(1)
            except Exception as e:
                logger.warning("check netapp job fail, retry in 5s, {}".format(e))
                time.sleep(5)
        if err_msg:
            raise ValueError(err_msg)

    def delete_volume(self, volume_name):
        vol_uuid = self._get_key_volumes(volume_name)
        vol_del_url = "https://{}/api/storage/volumes/{}".format(self.host_ip, vol_uuid)
        try:
            res_text = requests.delete(
                vol_del_url, headers=self.headers, timeout=ONTEP_API_TIMEOUT, json={}, verify=False
            ).json()
            if "error" in res_text:
                raise ValueError(res_text["message"])
        except Exception as e:
            logger.error("NetappDriver delete volume failed: {}".format(e))
            raise e
        self._check_job_status(res_text["job"]["uuid"])

    def _get_key_volumes(self, volume_name):
        volume_name = volume_name.replace("-", "_")
        try:
            _url = "https://{}/api/storage/volumes?name={}&svm.name={}".format(
                self.host_ip, volume_name, self.svm_name
            )
            volumes_info = requests.get(_url, headers=self.headers, timeout=ONTEP_API_TIMEOUT,
                                        verify=False).json()
            for volume in volumes_info["records"]:
                return volume["uuid"]
        except Exception as e:
            raise ValueError("NetappDriver get volume key failed, {}".format(e)) from e

    def update_volume_quota(self, volume_name, quota):
        if quota is None:
            quota = 0
        if not isinstance(quota, int):
            quota = int(quota)
        provision_size = quota * 1024 * 1024 * 1024
        volume_data = {
            "size": provision_size,
        }
        vol_uuid = self._get_key_volumes(volume_name)
        try:
            url = "https://{}/api/storage/volumes/{}".format(self.host_ip, vol_uuid)
            res_text = requests.patch(
                url, headers=self.headers, json=volume_data, timeout=ONTEP_API_TIMEOUT,
                verify=False
            ).json()
            if "error" in res_text:
                raise ValueError(res_text["error"])
        except Exception as e:
            logger.error("NetappDriver create volume failed, {}".format(e))
            raise e
        self._check_job_status(res_text["job"]["uuid"])
