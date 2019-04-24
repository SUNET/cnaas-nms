node {
    stage('Checkout') {
        git url: 'https://github.com/krihal/cnaas-nms.git'
        checkout scm
    }

    stage("Container - API") {
        app = docker.build("cnaas-nms/api", "./docker/api/")
    }

    stage("Container - DHCPD") {
        app = docker.build("cnaas-nms/dhcpd", "./docker/dhcpd/")
    }

    stage("Container - HTTPD") {
        app = docker.build("cnaas-nms/httpd", "./docker/httpd/")
    }

    stage("Unit test") {
	sh 'python3 -m pip install -r requirements.txt'
	sh 'nosetests-3.4 --xunitmp-file test_results.xml src/cnaas_nms/'
	junit keepLongStdio: true, allowEmptyResults: true, testResults: 'test_results.xml'
    }
}
