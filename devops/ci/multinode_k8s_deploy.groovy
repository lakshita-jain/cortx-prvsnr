def remote_host(hosts){
  remotes = []
  hosts = hosts.split("\n")
  println hosts[0].split(",")[0].split("=")[1]
  for (int num = 0; num < hosts.size(); num++) {
      remote_node = [:]
      remote_node.name = "node-" + num
      remote_node.host = hosts[0].split(",")[0].split("=")[1]
      remote_node.user = hosts[0].split(",")[1].split("=")[1]
      remote_node.password = hosts[0].split(",")[2].split("=")[1]
      remote_node.allowAnyHosts = true
      remotes[num] = remote_node
  }
  return remotes
}

pipeline {
    agent {
        node {
            label 'prvsnr_sanity_g4-rhev4-0658'
        }
    }

    // triggers { cron('30 19 * * *') }

    options {
        timeout(time: 240, unit: 'MINUTES')
        timestamps()
        buildDiscarder(logRotator(daysToKeepStr: '20', numToKeepStr: '20'))
    }

    environment {
        WORK_SPACE = "/root/cortx-k8s/k8_cortx_cloud"
        NODES_HOST = "$(cat ${hosts} | awk -F[,] '{print $1}' | cut -d'=' -f2)"
        PRIMARY_NODE = "$(head -1 ${hosts} | awk -F[,] '{print $1}' | cut -d'=' -f2)"
        WORKER_NODES = "$(cat ${hosts} | grep -v ${PRIMARY_NODE} | awk -F[,] '{print $1}' | cut -d'=' -f2)"
    }

    parameters {
        string(name: 'CORTX_SCRIPTS_REPO', defaultValue: 'https://github.com/Seagate/cortx-k8s', description: 'Repository for cortx-k8s scripts (Services Team)', trim: true)
        string(name: 'CORTX_SCRIPTS_BRANCH', defaultValue: 'cortx-test', description: 'cortx-k8s scripts (Provisioner Team)', trim: true)
        // string(name: 'SCRIPTS_REPO', defaultValue: 'https://github.com/ashukakkar/cortx-prvsnr-1', description: 'Repository for Cluster Setup scripts', trim: true)
        text(defaultValue: '''hostname=<hostname>,user=<user>,pass=<password>''', description: 'VM details to be used. First node will be used as Master', name: 'hosts')
    }

    stages {

        stage('Checkout Script') {
            remotes = remote_host(${hosts})
            for (remote in remotes) {
                sshCommand remote: remote, command: """
                    cd /root
                    git clone ${CORTX_SCRIPTS_REPO} -b ${CORTX_SCRIPTS_BRANCH}
                """
            }
        }

        stage('Update solution.yaml') {
            remotes = remote_host(${hosts})
            for (remote in remotes) {
                sshCommand remote: remote, command: """
                    rm -f ${WORK_SPACE}/solution.yaml
                    cp input/solution.yaml ${WORK_SPACE}/solution.yaml
                """
            }
        }

        // stage('Copy prereq and solution.yaml') {
        //     for (node in $WORKER_NODES){
        //         sshCommand remote: remotes[0], command: """
        //             scp -q $WORK_SPACE/solution.yaml "$node":./
        //             scp -q $WORK_SPACE/prereq-deploy-cortx-cloud.sh "$node":./
        //         """
        //     }
        // }

        stage('Run prerequisite script') {
            remotes = remote_host(${hosts})
            for (remote in remotes) {
                sshCommand remote: remote, command: """
                    sh '${WORK_SPACE}/prereq-deploy-cortx-cloud.sh /dev/sdb' 
                """
            }
        }

        stage('Deploy CORTX Cluster') {
            sshCommand remote: remotes[0], command: """
                sh '${WORK_SPACE}/deploy-cortx-cloud.sh'
            """
        }
    }

    post {

        success {
            script {
                sshCommand remote: remotes[0], command: """
                    kubectl get pods
                """
            }
        }

        // failure {
        //     script {}
        // }

        always {
            script {
                def recipientProvidersClass = [[$class: 'RequesterRecipientProvider']]
                // mailRecipients = "shailesh.vaidya@seagate.com"
                emailext ( 
                    body: '''${SCRIPT, template="cluster-setup-email.template"}''',
                    mimeType: 'text/html',
                    subject: "[Jenkins Build ${currentBuild.currentResult}] : ${env.JOB_NAME}",
                    attachLog: true,
                    to: "${mailRecipients}",
                    recipientProviders: recipientProvidersClass
                )
                cleanWs()
            }
        }
    }
}
