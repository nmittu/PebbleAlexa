Pebble.addEventListener('showConfiguration', function(e) {
    // Show config page
	Pebble.openURL('https://pebblealexa.com/auth');
});

Pebble.addEventListener('webviewclosed', function(e) {
    localStorage.setItem("uid", encodeURIComponent(e.response));
		console.log("yoo")
});

Pebble.addEventListener('appmessage',
    function(e){
			console.log(JSON.stringify(e));
        if(localStorage.getItem("uid")){
					var xhr = new XMLHttpRequest();
					var url = "https://pebblealexa.com/text/" + encodeURIComponent(e.payload.STRING);
					var params = "uid=" + localStorage.getItem("uid");
					xhr.open("POST", url, true);
					xhr.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
					xhr.onreadystatechange = function() {
						if(xhr.readyState == 4 && xhr.status == 200){
							Pebble.sendAppMessage({STRING: xhr.responseText},
								function(e){
									console.log(e.payload.STRING + " : " + xhr.responseText);
								},
								function(e){
									console.log('Error Sending string To Pebble');
								}
							);
						}else{
							Pebble.sendAppMessage({STRING: "Login To Amazon Account!"},
								function(e){
									console.log('string Sent');
								},
								function(e){
									console.log('Error Sending string To Pebble');
								}
							);
						}
					}
					xhr.send(params);
					
				}else{
					Pebble.sendAppMessage({STRING: "Login To Amazon Account!"},
						function(e){
							console.log('string Sent');
						},
						function(e){
							console.log('Error Sending string To Pebble');
						}
					);
				}
    }
);